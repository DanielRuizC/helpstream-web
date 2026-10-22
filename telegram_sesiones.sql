-- ========================================================================
-- HELPSTREAM: GESTIÓN DE ESTADO STATELESS PARA BOT DE TELEGRAM
-- ========================================================================
-- Este script crea la tabla `telegram_sesiones` en Supabase (PostgreSQL)
-- para almacenar el estado del flujo conversacional de registro de tickets.
--
-- Ejecutar en: Supabase Dashboard -> SQL Editor
-- ========================================================================

-- 1. Crear tabla telegram_sesiones
CREATE TABLE IF NOT EXISTS public.telegram_sesiones (
    chat_id BIGINT PRIMARY KEY,
    correo_usuario TEXT NULL,
    paso_actual TEXT NOT NULL DEFAULT 'menu_principal',
    datos_temporales JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Índices y comentarios descriptivos
COMMENT ON TABLE public.telegram_sesiones IS 'Almacena el estado conversacional temporal de usuarios en Telegram para HelpStream.';
COMMENT ON COLUMN public.telegram_sesiones.chat_id IS 'ID único del chat/usuario en Telegram (clave primaria).';
COMMENT ON COLUMN public.telegram_sesiones.correo_usuario IS 'Correo corporativo validado del solicitante.';
COMMENT ON COLUMN public.telegram_sesiones.paso_actual IS 'Fase actual: menu_principal, esperando_correo_registro, esperando_descripcion, esperando_sede, esperando_piso, esperando_correo_estado.';
COMMENT ON COLUMN public.telegram_sesiones.datos_temporales IS 'Datos temporales en formato JSONB (ej. descripción del ticket, sede, piso).';

-- 3. Función y Trigger para actualización automática de updated_at
CREATE OR REPLACE FUNCTION public.actualizar_updated_at_telegram_sesiones()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_actualizar_updated_at_telegram_sesiones ON public.telegram_sesiones;
CREATE TRIGGER trg_actualizar_updated_at_telegram_sesiones
    BEFORE UPDATE ON public.telegram_sesiones
    FOR EACH ROW
    EXECUTE FUNCTION public.actualizar_updated_at_telegram_sesiones();

-- 4. Seguridad a Nivel de Fila (Row Level Security - RLS)
ALTER TABLE public.telegram_sesiones ENABLE ROW LEVEL SECURITY;

-- Permitir acceso completo al rol de servicio del backend (SUPABASE_SERVICE_ROLE_KEY)
DROP POLICY IF EXISTS "Acceso total service_role telegram_sesiones" ON public.telegram_sesiones;
CREATE POLICY "Acceso total service_role telegram_sesiones"
    ON public.telegram_sesiones
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
