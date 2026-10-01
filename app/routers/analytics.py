from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .. import models, schemas
from ..database import get_db
from .auth import get_current_admin_user
from .reportes import calcular_metrica_ticket

router = APIRouter(
    prefix="/api/analytics",
    tags=["HelpStream Analytics"]
)

# Tiempo promedio histórico de resolución en horas por técnico (HU15.1)
TIEMPO_PROMEDIO_HISTORICO_HORAS = 1.5

CATEGORIAS_PATRONES = {
    "Red y Conectividad": ["red", "wifi", "internet", "conexion", "caida", "enlace", "vpn"],
    "Impresoras y Periféricos": ["impresora", "papel", "toner", "scanner", "escaner", "teclado", "mouse", "monitor"],
    "Cuentas y Accesos": ["clave", "password", "correo", "login", "acceso", "bloqueo", "cuenta", "usuario"],
    "Maquinaria y Planta": ["caldera", "fuga", "presion", "motor", "sensor", "planta", "valvula", "tanque"],
    "Servidores e Infraestructura": ["servidor", "base de datos", "disco", "backup", "datacenter", "memoria", "cpu"],
    "Sistemas y Software": ["sistema", "software", "aplicacion", "erp", "sap", "error", "pantalla", "lento"]
}

NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

RANGOS_HORARIOS = [
    ("08:00 - 10:00", 8, 10),
    ("10:00 - 12:00", 10, 12),
    ("12:00 - 14:00", 12, 14),
    ("14:00 - 16:00", 14, 16),
    ("16:00 - 18:00", 16, 18),
    ("18:00 - 20:00", 18, 20),
    ("20:00 - 24:00", 20, 24)
]


def es_autoatencion(ticket: models.Ticket) -> bool:
    """Identifica si el ticket fue resuelto mediante autoatención / microaprendizaje (HU15.1)."""
    if ticket.comentario_tecnico:
        com_lower = ticket.comentario_tecnico.lower()
        if "video" in com_lower or "autoatencion" in com_lower or "microaprendizaje" in com_lower:
            return True
    return False


def categorizar_incidente(descripcion: Optional[str]) -> str:
    """Clasifica la incidencia según palabras clave o temas recurrentes."""
    if not descripcion:
        return "Incidencias Generales"
    desc_lower = descripcion.lower()
    for cat, kws in CATEGORIAS_PATRONES.items():
        for kw in kws:
            if kw in desc_lower:
                return cat
    palabras = [w for w in desc_lower.split() if len(w) > 3]
    if palabras:
        return f"Incidencia {palabras[0].capitalize()}"
    return "Incidencias Generales"


def obtener_rango_horario(hora: int) -> str:
    """Mapea una hora del día a su franja horaria correspondiente."""
    for nombre, h_ini, h_fin in RANGOS_HORARIOS:
        if h_ini <= hora < h_fin:
            return nombre
    if hora < 8:
        return "08:00 - 10:00"
    return "20:00 - 24:00"


def calcular_metricas_analytics(
    db: Session,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    anio: Optional[int] = None
) -> Dict[str, Any]:
    """
    Función central de cálculo de métricas para HelpStream Analytics.
    Calcula KPIs, series temporales, Top 5 de incidentes, mapa de calor y resumen mensual
    aplicando filtros opcionales de fecha_inicio, fecha_fin y anio.
    """
    ahora = datetime.utcnow()
    query = db.query(models.Ticket)

    # Identificar todos los años disponibles en la base de datos
    todos_tickets = db.query(models.Ticket.fecha_creacion).all()
    anios_set = set()
    for (fc,) in todos_tickets:
        if fc:
            anios_set.add(fc.year)
    anios_set.add(ahora.year)
    anios_disponibles = sorted(list(anios_set), reverse=True)

    anio_seleccionado = anio or (anios_disponibles[0] if anios_disponibles else ahora.year)

    # Filtrado dinámico por fechas
    if fecha_inicio:
        try:
            dt_inicio = datetime.strptime(fecha_inicio.strip(), "%Y-%m-%d")
            query = query.filter(models.Ticket.fecha_creacion >= dt_inicio)
        except ValueError:
            pass

    if fecha_fin:
        try:
            dt_fin = datetime.strptime(fecha_fin.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(models.Ticket.fecha_creacion <= dt_fin)
        except ValueError:
            pass

    # Si se especificó solo el año sin rango de días explícito
    if not fecha_inicio and not fecha_fin and anio:
        dt_inicio = datetime(anio, 1, 1, 0, 0, 0)
        dt_fin = datetime(anio, 12, 31, 23, 59, 59)
        query = query.filter(models.Ticket.fecha_creacion >= dt_inicio, models.Ticket.fecha_creacion <= dt_fin)

    tickets_periodo = query.order_by(models.Ticket.fecha_creacion.asc()).all()

    # ==========================================
    # 1. CÁLCULO DE KPIS GERENCIALES
    # ==========================================
    total_tickets = len(tickets_periodo)
    tickets_autoatencion = 0
    tickets_resueltos = 0
    tickets_reabiertos = 0
    tiempos_resolucion = []
    tickets_fcr_count = 0

    for t in tickets_periodo:
        es_auto = es_autoatencion(t)
        if es_auto:
            tickets_autoatencion += 1

        comentario = (t.comentario_tecnico or "").lower()
        es_reabierto = "reabier" in comentario or "insistencia" in comentario
        if es_reabierto:
            tickets_reabiertos += 1

        if t.estado == "Resuelto":
            tickets_resueltos += 1
            if not es_reabierto:
                tickets_fcr_count += 1

            sla_info = calcular_metrica_ticket(t, ahora)
            sla_limite = sla_info.get("sla_limite_horas", 72)
            tiempo_calc = min(sla_info.get("tiempo_transcurrido_horas", 2.0), sla_limite)
            if tiempo_calc <= 0:
                tiempo_calc = 1.5
            tiempos_resolucion.append(tiempo_calc)

    horas_ahorradas = round(tickets_autoatencion * TIEMPO_PROMEDIO_HISTORICO_HORAS, 1)
    mttr_horas = round(sum(tiempos_resolucion) / len(tiempos_resolucion), 1) if tiempos_resolucion else 2.5
    fcr_porcentaje = round((tickets_fcr_count / total_tickets * 100), 1) if total_tickets > 0 else 0.0
    ratio_reabiertos = round((tickets_reabiertos / total_tickets * 100), 1) if total_tickets > 0 else 0.0

    kpis = {
        "horas_ahorradas": horas_ahorradas,
        "tickets_autoatencion": tickets_autoatencion,
        "tiempo_promedio_historico": TIEMPO_PROMEDIO_HISTORICO_HORAS,
        "mttr_horas": mttr_horas,
        "fcr_porcentaje": fcr_porcentaje,
        "ratio_reabiertos_porcentaje": ratio_reabiertos,
        "tickets_reabiertos": tickets_reabiertos,
        "total_tickets": total_tickets,
        "tickets_resueltos": tickets_resueltos
    }

    # ==========================================
    # 2. DATOS PARA GRÁFICOS (CHART.JS)
    # ==========================================
    # A. Serie de tiempo: Soporte Técnico vs Autoatención (HU15.2)
    agrupacion_tiempo = defaultdict(lambda: {"soporte": 0, "autoatencion": 0})
    for t in tickets_periodo:
        fc = t.fecha_creacion or ahora
        fecha_str = fc.strftime("%Y-%m-%d")
        if es_autoatencion(t):
            agrupacion_tiempo[fecha_str]["autoatencion"] += 1
        else:
            agrupacion_tiempo[fecha_str]["soporte"] += 1

    fechas_ordenadas = sorted(agrupacion_tiempo.keys())
    serie_tiempo = {
        "labels": fechas_ordenadas if fechas_ordenadas else [ahora.strftime("%Y-%m-%d")],
        "soporte_tecnico": [agrupacion_tiempo[f]["soporte"] for f in fechas_ordenadas] if fechas_ordenadas else [0],
        "autoatencion": [agrupacion_tiempo[f]["autoatencion"] for f in fechas_ordenadas] if fechas_ordenadas else [0]
    }

    # B. Top 5 de Incidentes Recurrentes
    conteo_categorias = defaultdict(int)
    for t in tickets_periodo:
        cat = categorizar_incidente(t.descripcion)
        conteo_categorias[cat] += 1

    top_categorias = sorted(
        [{"categoria": k, "total": v} for k, v in conteo_categorias.items()],
        key=lambda x: x["total"],
        reverse=True
    )[:5]

    # C. Mapa de Calor (Día de la semana vs Rango horario)
    matriz_mapa = {dia: {r[0]: 0 for r in RANGOS_HORARIOS} for dia in DIAS_SEMANA}
    max_demanda = 0

    for t in tickets_periodo:
        fc = t.fecha_creacion or ahora
        dia_idx = fc.weekday()  # 0 = Lunes, 6 = Domingo
        dia_nombre = DIAS_SEMANA[dia_idx]
        rango = obtener_rango_horario(fc.hour)
        matriz_mapa[dia_nombre][rango] += 1
        if matriz_mapa[dia_nombre][rango] > max_demanda:
            max_demanda = matriz_mapa[dia_nombre][rango]

    nombres_rangos = [r[0] for r in RANGOS_HORARIOS]
    mapa_calor = {
        "dias": DIAS_SEMANA,
        "rangos": nombres_rangos,
        "max_valor": max(max_demanda, 1),
        "datos": [
            {
                "dia": dia,
                "valores": [matriz_mapa[dia][rng] for rng in nombres_rangos]
            }
            for dia in DIAS_SEMANA
        ]
    }

    # ==========================================
    # 3. RESUMEN MENSUAL DEL PERÍODO / AÑO
    # ==========================================
    if fecha_inicio or fecha_fin:
        mensual_dict = defaultdict(lambda: {"total": 0, "resueltos": 0, "vencidos_sla": 0, "autoatencion": 0})
        anios_meses_presentes = set()
        for t in tickets_periodo:
            fc = t.fecha_creacion or ahora
            clave = (fc.year, fc.month)
            anios_meses_presentes.add(clave)
            mensual_dict[clave]["total"] += 1
            if t.estado == "Resuelto":
                mensual_dict[clave]["resueltos"] += 1

            sla = calcular_metrica_ticket(t, ahora)
            if sla.get("esta_vencido"):
                mensual_dict[clave]["vencidos_sla"] += 1

            if es_autoatencion(t):
                mensual_dict[clave]["autoatencion"] += 1

        resumen_mensual = []
        for anio_m, mes_num in sorted(list(anios_meses_presentes)):
            data_m = mensual_dict[(anio_m, mes_num)]
            tot = data_m["total"]
            pct_sla = round(((tot - data_m["vencidos_sla"]) / tot) * 100, 1) if tot > 0 else 100.0

            resumen_mensual.append({
                "mes": NOMBRES_MESES[mes_num - 1],
                "mes_num": mes_num,
                "anio": anio_m,
                "total_atenciones": tot,
                "incidentes_resueltos": data_m["resueltos"],
                "cumplimiento_sla_porcentaje": pct_sla,
                "horas_ahorradas": round(data_m["autoatencion"] * TIEMPO_PROMEDIO_HISTORICO_HORAS, 1)
            })
    else:
        tickets_anio = db.query(models.Ticket).filter(
            models.Ticket.fecha_creacion >= datetime(anio_seleccionado, 1, 1),
            models.Ticket.fecha_creacion <= datetime(anio_seleccionado, 12, 31, 23, 59, 59)
        ).all()

        mensual_dict = defaultdict(lambda: {"total": 0, "resueltos": 0, "vencidos_sla": 0, "autoatencion": 0})
        for t in tickets_anio:
            fc = t.fecha_creacion or ahora
            m = fc.month
            mensual_dict[m]["total"] += 1
            if t.estado == "Resuelto":
                mensual_dict[m]["resueltos"] += 1

            sla = calcular_metrica_ticket(t, ahora)
            if sla.get("esta_vencido"):
                mensual_dict[m]["vencidos_sla"] += 1

            if es_autoatencion(t):
                mensual_dict[m]["autoatencion"] += 1

        resumen_mensual = []
        for mes_num in range(1, 13):
            data_m = mensual_dict[mes_num]
            tot = data_m["total"]
            pct_sla = 100.0
            if tot > 0:
                pct_sla = round(((tot - data_m["vencidos_sla"]) / tot) * 100, 1)

            resumen_mensual.append({
                "mes": NOMBRES_MESES[mes_num - 1],
                "mes_num": mes_num,
                "anio": anio_seleccionado,
                "total_atenciones": tot,
                "incidentes_resueltos": data_m["resueltos"],
                "cumplimiento_sla_porcentaje": pct_sla,
                "horas_ahorradas": round(data_m["autoatencion"] * TIEMPO_PROMEDIO_HISTORICO_HORAS, 1)
            })

    return {
        "filtros_aplicados": {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "anio": anio_seleccionado,
            "total_tickets_periodo": total_tickets
        },
        "anios_disponibles": anios_disponibles,
        "kpis": kpis,
        "graficos": {
            "soporte_vs_autoatencion": serie_tiempo,
            "top_incidentes_recurrentes": top_categorias,
            "mapa_calor": mapa_calor
        },
        "resumen_mensual": resumen_mensual
    }


@router.get("/dashboard")
def get_analytics_dashboard(
    fecha_inicio: Optional[str] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    fecha_fin: Optional[str] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    anio: Optional[int] = Query(None, description="Año a filtrar (ej. 2026)"),
    db: Session = Depends(get_db),
    admin_user: models.Usuario = Depends(get_current_admin_user)
):
    """
    HU15: Endpoint central de HelpStream Analytics.
    Proporciona KPIs dinámicos, series temporales para Chart.js, Top 5 de incidentes,
    mapa de calor de demanda y tabla de resumen mensual con filtros de fecha y año.
    Protegido con get_current_admin_user (403 Forbidden para usuarios no administradores).
    """
    return calcular_metricas_analytics(db=db, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, anio=anio)

