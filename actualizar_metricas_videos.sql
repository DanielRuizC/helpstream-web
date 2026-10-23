-- ========================================================================
-- HELPSTREAM: MÉTRICAS DE MICROAPRENDIZAJE / VIDEOS TUTORIALES
-- ========================================================================
-- Este script agrega las columnas `reproducciones` y `casos_resueltos`
-- a la tabla de videos tutoriales en Supabase (PostgreSQL).
--
-- Ejecutar en: Supabase Dashboard -> SQL Editor
-- ========================================================================

-- 1. Agregar columnas a la tabla principal 'videos_tutoriales'
ALTER TABLE IF EXISTS public.videos_tutoriales
    ADD COLUMN IF NOT EXISTS reproducciones INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS casos_resueltos INTEGER NOT NULL DEFAULT 0;

-- 2. Documentar las columnas
COMMENT ON COLUMN public.videos_tutoriales.reproducciones IS 'Cantidad de veces que el video tutorial ha sido visualizado/reproducido por usuarios.';
COMMENT ON COLUMN public.videos_tutoriales.casos_resueltos IS 'Cantidad de veces que el video tutorial resolvió la incidencia directamente (clic en "Solucioné mi problema").';

-- 3. Compatibilidad: Si en algún entorno la tabla fue nombrada como 'microaprendizaje'
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'microaprendizaje') THEN
        ALTER TABLE public.microaprendizaje 
            ADD COLUMN IF NOT EXISTS reproducciones INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS casos_resueltos INTEGER NOT NULL DEFAULT 0;

        COMMENT ON COLUMN public.microaprendizaje.reproducciones IS 'Cantidad de veces que el video ha sido visto.';
        COMMENT ON COLUMN public.microaprendizaje.casos_resueltos IS 'Cantidad de incidencias resueltas vía botón "Solucioné mi problema".';
    END IF;
END $$;
