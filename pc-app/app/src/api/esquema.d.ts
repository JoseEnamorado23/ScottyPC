// Generado por `npm run generar-tipos` a partir de /openapi.json. No editar.

export interface paths {
    "/salud": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Estado del servidor */
        get: operations["salud_salud_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/apagar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apaga el servidor */
        post: operations["apagar_apagar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lista los proyectos */
        get: operations["listar_proyectos_get"];
        put?: never;
        /**
         * Crea un proyecto a partir de un archivo
         * @description Copia el archivo (el original no se modifica) y devuelve hojas, columnas y vista previa.
         */
        post: operations["crear_proyectos_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Obtiene un proyecto */
        get: operations["obtener_proyectos__proyecto_id__get"];
        put?: never;
        post?: never;
        /** Elimina un proyecto y su carpeta */
        delete: operations["eliminar_proyectos__proyecto_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/revision": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Revisión guardada */
        get: operations["obtener_revision_proyectos__proyecto_id__revision_get"];
        put?: never;
        /** Valida y revisa el dataset */
        post: operations["revision_proyectos__proyecto_id__revision_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/datos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Vista previa de una hoja */
        get: operations["datos_proyectos__proyecto_id__datos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/distribucion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Distribución de una columna
         * @description Sobre todas las filas: conteos por valor o histograma si es numérica con muchos valores.
         */
        get: operations["distribucion_proyectos__proyecto_id__distribucion_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/decisiones/previsualizar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Decisiones que resultan de las acciones elegidas
         * @description Las calcula el núcleo; no guarda nada. Los hallazgos sin elección usan la acción sugerida.
         */
        post: operations["previsualizar_decisiones_proyectos__proyecto_id__decisiones_previsualizar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/decisiones/plantilla": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Decisiones sugeridas */
        get: operations["plantilla_decisiones_proyectos__proyecto_id__decisiones_plantilla_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/decisiones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Decisiones guardadas */
        get: operations["obtener_decisiones_proyectos__proyecto_id__decisiones_get"];
        /**
         * Valida y guarda las decisiones
         * @description Invalida la preparación y las etapas posteriores. Los errores (422) indican el campo.
         */
        put: operations["guardar_decisiones_proyectos__proyecto_id__decisiones_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/preparar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Prepara los datos
         * @description La separación elegida se guarda en la receta (su única fuente). Rehacer la
         *     preparación deja desactualizadas la recomendación, la configuración de PC y el
         *     análisis, pero no las decisiones.
         */
        post: operations["preparar_proyectos__proyecto_id__preparar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/preparacion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resumen de la preparación vigente y separación inicial del formulario */
        get: operations["estado_preparacion_proyectos__proyecto_id__preparacion_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/recomendacion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Recomendación guardada */
        get: operations["obtener_recomendacion_proyectos__proyecto_id__recomendacion_get"];
        put?: never;
        /** Lanza la recomendación de prueba (trabajo) */
        post: operations["recomendacion_proyectos__proyecto_id__recomendacion_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/recomendacion/evaluar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Advertencias sobre la prueba y el max_k elegidos
         * @description Compara la elección con la recomendación guardada; no guarda nada.
         */
        post: operations["evaluar_prueba_proyectos__proyecto_id__recomendacion_evaluar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/configuracion-pc/plantilla": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Plantilla de la configuración de PC (para restablecer) */
        get: operations["plantilla_configuracion_pc_proyectos__proyecto_id__configuracion_pc_plantilla_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/configuracion-pc/validar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Valida la configuración de PC sin guardarla
         * @description Todos los errores (con su campo) y las advertencias, p. ej. si el objetivo no está al final.
         */
        post: operations["validar_configuracion_pc_proyectos__proyecto_id__configuracion_pc_validar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/configuracion-pc": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Configuración de PC (o la plantilla si aún no existe) */
        get: operations["configuracion_pc_proyectos__proyecto_id__configuracion_pc_get"];
        /** Valida y guarda la configuración de PC */
        put: operations["guardar_configuracion_pc_proyectos__proyecto_id__configuracion_pc_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/pc": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Lanza el análisis PC (trabajo) */
        post: operations["pc_proyectos__proyecto_id__pc_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/resultado": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resultado del análisis */
        get: operations["resultado_proyectos__proyecto_id__resultado_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/resultado/versiones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Versiones del resultado (original y ajustadas)
         * @description La primera consulta de un resultado anterior a las versiones lo migra (``migrada``).
         */
        get: operations["versiones_proyectos__proyecto_id__resultado_versiones_get"];
        put?: never;
        /**
         * Guarda el ajuste como una versión nueva y la hace actual
         * @description Las versiones anteriores (y pc.json) no se modifican.
         */
        post: operations["guardar_version_proyectos__proyecto_id__resultado_versiones_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/resultado/reagregar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Previsualiza el resultado con otro umbral u otras orientaciones (no guarda nada)
         * @description Sin volver a ejecutar PC: parte de las cuentas del bootstrap. 422 con el campo de cada
         *     problema (p. ej. ``orientaciones_manuales.0`` si contradice los niveles).
         */
        post: operations["reagregar_proyectos__proyecto_id__resultado_reagregar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/resultado/version-actual": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Cambia la versión actual del resultado */
        put: operations["cambiar_version_actual_proyectos__proyecto_id__resultado_version_actual_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/resultado/procedencia": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Datos, decisiones, separación y configuración que produjeron el resultado */
        get: operations["procedencia_proyectos__proyecto_id__resultado_procedencia_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/archivos/{nombre}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Descarga un archivo de resultados
         * @description Solo grafo.png, aristas.csv, mascara.csv, matriz_frecuencias.csv y resultado.json.
         *
         *     Requiere el encabezado X-Token: desde el navegador, descárguelo con fetch y
         *     muéstrelo con URL.createObjectURL (una etiqueta <img> no envía el encabezado).
         */
        get: operations["archivo_proyectos__proyecto_id__archivos__nombre__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/exportar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Exporta los resultados
         * @description Archivos de una versión, la receta e ``informe.html`` (autocontenido, se abre sin conexión).
         */
        post: operations["exportar_proyectos__proyecto_id__exportar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/modelo-causal/aplicabilidad": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Comprueba si se puede construir el modelo causal (no construye nada)
         * @description Bloqueantes y advertencias, cada uno con la acción que lo resuelve y la pantalla donde se hace.
         */
        post: operations["aplicabilidad_modelo_proyectos__proyecto_id__modelo_causal_aplicabilidad_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/modelo-causal": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Modelo causal y su evaluación */
        get: operations["modelo_causal_proyectos__proyecto_id__modelo_causal_get"];
        put?: never;
        /**
         * Construye el modelo causal (trabajo)
         * @description 409 con ``detalles.problemas`` si hay bloqueantes. Usa la versión actual del resultado de PC.
         */
        post: operations["construir_modelo_causal_proyectos__proyecto_id__modelo_causal_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/modelo-causal/casos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Filas de test en unidades originales (para elegir un caso) */
        get: operations["casos_modelo_proyectos__proyecto_id__modelo_causal_casos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/modelo-causal/contrafactual": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Escenario «¿qué pasa si…?» sobre un caso
         * @description El caso es una fila de test (``indice_test``) o valores propios (``valores``, unidades originales).
         *     422 si una intervención no es válida (p. ej. sobre el objetivo o una consecuencia suya).
         */
        post: operations["contrafactual_modelo_proyectos__proyecto_id__modelo_causal_contrafactual_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/condiciones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Condiciones para prescribir
         * @description Con la configuración enviada o, si no se envía, con la guardada (o la sugerida).
         */
        post: operations["condiciones_proyectos__proyecto_id__prescripcion_condiciones_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/configuracion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Configuración de la prescripción
         * @description La guardada o, si no hay, la sugerida (``guardada: false``) con las modificables de pc.json.
         */
        get: operations["configuracion_proyectos__proyecto_id__prescripcion_configuracion_get"];
        /**
         * Guarda la configuración
         * @description Solo desactualiza la etapa de prescripción (sus lotes y evaluaciones se archivan).
         */
        put: operations["guardar_proyectos__proyecto_id__prescripcion_configuracion_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/configuracion/validar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Valida sin guardar */
        post: operations["validar_proyectos__proyecto_id__prescripcion_configuracion_validar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/calibrar-mu": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Calibra μ con train (trabajo) */
        post: operations["calibrar_proyectos__proyecto_id__prescripcion_calibrar_mu_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/caso": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Prescripción de un caso
         * @description 409 ``MU_SIN_CALIBRAR`` si μ es automático y no se calibró; 409 ``PRESCRIPCION_BLOQUEADA`` con
         *     los problemas si hay bloqueantes.
         */
        post: operations["caso_proyectos__proyecto_id__prescripcion_caso_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/lote": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Prescripción por lote (trabajo)
         * @description «test»: los casos de test que no cumplen el objetivo. «csv»: un archivo con las columnas
         *     originales, preparado con la receta (las filas que no se pueden preparar se informan).
         */
        post: operations["lote_proyectos__proyecto_id__prescripcion_lote_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/lotes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lotes guardados */
        get: operations["lotes_proyectos__proyecto_id__prescripcion_lotes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/lotes/{numero}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resultados de un lote (paginados) */
        get: operations["resultados_lote_proyectos__proyecto_id__prescripcion_lotes__numero__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/evaluacion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Evalúa el prescriptor sobre test (trabajo) */
        post: operations["evaluacion_proyectos__proyecto_id__prescripcion_evaluacion_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/evaluaciones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Evaluaciones guardadas */
        get: operations["evaluaciones_proyectos__proyecto_id__prescripcion_evaluaciones_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/evaluaciones/{numero}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Informe de una evaluación */
        get: operations["informe_evaluacion_proyectos__proyecto_id__prescripcion_evaluaciones__numero__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/proyectos/{proyecto_id}/prescripcion/exportar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** CSV de prescripciones e informe HTML */
        post: operations["exportar_proyectos__proyecto_id__prescripcion_exportar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/trabajos/{trabajo_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Estado y progreso de un trabajo */
        get: operations["estado_trabajos__trabajo_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/trabajos/{trabajo_id}/cancelar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancela un trabajo en curso */
        post: operations["cancelar_trabajos__trabajo_id__cancelar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/trabajos/{trabajo_id}/reanudar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reanuda un trabajo
         * @description Un análisis PC continúa desde su punto de control; una recomendación se repite.
         */
        post: operations["reanudar_trabajos__trabajo_id__reanudar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AccionHallazgo */
        AccionHallazgo: {
            /** Accion */
            accion: string;
            /**
             * Opciones
             * @default []
             */
            opciones: string[];
            /**
             * Descripcion
             * @default
             */
            descripcion: string;
            /**
             * Requiere Confirmacion
             * @default false
             */
            requiere_confirmacion: boolean;
        };
        /** AccionPrescrita */
        AccionPrescrita: {
            /** Variable */
            variable: string;
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "continua" | "discreta";
            /** Antes */
            antes: unknown;
            /** Despues */
            despues: unknown;
            /** Antes Numerico */
            antes_numerico: number | null;
            /** Despues Numerico */
            despues_numerico: number | null;
            /** Cambio */
            cambio: number | null;
            /**
             * Contribucion
             * @description Cuánto baja el logro si se quita solo esta acción.
             */
            contribucion: number;
            /** Restriccion Activa */
            restriccion_activa: string | null;
            /** Extrapolacion */
            extrapolacion: boolean;
            /**
             * Mantener
             * @description Intermedia que se mantiene constante (cambio despreciable).
             */
            mantener: boolean;
        };
        /** AdvertenciaEleccion */
        AdvertenciaEleccion: {
            /** Codigo */
            codigo: string;
            /** Campo */
            campo: string;
            /** Mensaje */
            mensaje: string;
            /**
             * Nivel
             * @enum {string}
             */
            nivel: "advertencia" | "info";
        };
        /** Agregacion */
        Agregacion: {
            /** Umbral Frecuencia */
            umbral_frecuencia: number;
            /** Orientaciones Manuales */
            orientaciones_manuales: components["schemas"]["OrientacionManual"][];
        };
        /** AlternativaPrueba */
        AlternativaPrueba: {
            /** Prueba */
            prueba: string;
            /** Ventajas */
            ventajas: string;
            /** Desventajas */
            desventajas: string;
        };
        /** Apagado */
        Apagado: {
            /** Mensaje */
            mensaje: string;
        };
        /** Aplicabilidad */
        Aplicabilidad: {
            /** Problemas */
            problemas: components["schemas"]["ProblemaAplicabilidad"][];
            /** Bloqueado */
            bloqueado: boolean;
            /** Version Resultado */
            version_resultado: number | null;
            subgrafo: components["schemas"]["SubgrafoObjetivo"] | null;
        };
        /** AristaAgregada */
        AristaAgregada: {
            /** Origen */
            origen: string;
            /** Destino */
            destino: string;
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "dirigida" | "sin_orientar" | "manual";
            /** Frecuencia Total */
            frecuencia_total: number;
            /** Frecuencia Origen Destino */
            frecuencia_origen_destino: number;
            /** Frecuencia Destino Origen */
            frecuencia_destino_origen: number;
            /** Frecuencia Sin Orientar */
            frecuencia_sin_orientar: number;
            /** Spearman */
            spearman: number | null;
            /** Signo */
            signo: number;
            /** Justificacion */
            justificacion: string | null;
        };
        /** AvisoContrafactual */
        AvisoContrafactual: {
            /** Codigo */
            codigo: string;
            /** Mensaje */
            mensaje: string;
            /** Variables */
            variables: string[];
        };
        /** AvisoResultado */
        AvisoResultado: {
            /** Codigo */
            codigo: string;
            /**
             * Nivel
             * @enum {string}
             */
            nivel: "advertencia" | "info";
            /** Titulo */
            titulo: string;
            /** Mensaje */
            mensaje: string;
            /** Variables */
            variables: string[];
            /** Pares */
            pares: components["schemas"]["ParVariables"][];
        };
        /** Calibracion */
        Calibracion: {
            /** Cv */
            cv: components["schemas"]["PuntoCalibracion"][];
            /** Test */
            test: components["schemas"]["PuntoCalibracion"][];
        };
        /** CalibracionMu */
        CalibracionMu: {
            /** Mu */
            mu: number;
            /** Rejilla */
            rejilla: components["schemas"]["PuntoRejilla"][];
            /** Casos */
            casos: number;
            /** Alcanzables */
            alcanzables: number;
            /** No Alcanzables */
            no_alcanzables: number;
            /** Casos Que Ya Cumplen */
            casos_que_ya_cumplen: number;
            /** Exito Requerido */
            exito_requerido: number;
            /** Advertencia */
            advertencia: string | null;
            /** Nota */
            nota: string;
            /** Calibrada En */
            calibrada_en?: string | null;
        };
        /** CandidatoMecanismo */
        CandidatoMecanismo: {
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "simple" | "complejo";
            /** Familia */
            familia: string;
            /** Puntuacion Cv */
            puntuacion_cv: number | null;
            /** Umbral Cv */
            umbral_cv: number | null;
            /** Error */
            error: string | null;
            /** Rescate */
            rescate: string[];
            /** Nombre Familia */
            nombre_familia: string;
        };
        /** Caracterizacion */
        Caracterizacion: {
            /** Objetivo */
            objetivo: string;
            /** Variables */
            variables: components["schemas"]["CaracterizacionVariable"][];
            /** Candidatas Prescriptivas */
            candidatas_prescriptivas: string[];
            /** Mensaje */
            mensaje: string;
        };
        /** CaracterizacionVariable */
        CaracterizacionVariable: {
            /** Variable */
            variable: string;
            /**
             * Categoria
             * @enum {string}
             */
            categoria: "causa_directa" | "causa_indirecta" | "consecuencia" | "ambigua" | "sin_camino";
            /** A Traves De */
            a_traves_de: string[];
            /** Frecuencia Con Objetivo */
            frecuencia_con_objetivo: number;
            /** Grupo Redundante */
            grupo_redundante: string[] | null;
            /** Modificable */
            modificable: boolean;
        };
        /** CasoEntrada */
        CasoEntrada: {
            /**
             * Indice Test
             * @description Fila de test (índice de «casos»).
             */
            indice_test?: number | null;
            /**
             * Valores
             * @description Valores propios en unidades originales.
             */
            valores?: {
                [key: string]: unknown;
            } | null;
        };
        /** CasoTest */
        CasoTest: {
            /**
             * Indice
             * @description Posición de la fila en los datos originales.
             */
            indice: number;
            /**
             * Valores
             * @description Por control, en unidades originales.
             */
            valores: {
                [key: string]: unknown;
            };
            /** Objetivo */
            objetivo: unknown;
        };
        /** CasosModelo */
        CasosModelo: {
            /** Total */
            total: number;
            /** Pagina */
            pagina: number;
            /** Por Pagina */
            por_pagina: number;
            /** Filas */
            filas: components["schemas"]["CasoTest"][];
        };
        /** Categoria */
        Categoria: {
            /** Valor */
            valor: unknown;
            /** Conteo */
            conteo: number;
            /** Porcentaje */
            porcentaje: number;
        };
        /** ClaseObjetivo */
        ClaseObjetivo: {
            /** Valor */
            valor: unknown;
            /** Conteo */
            conteo: number;
            /** Porcentaje */
            porcentaje: number;
        };
        /** Codificacion */
        Codificacion: {
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "binaria" | "ordinal" | "one_hot" | "agrupacion";
            /** Orden */
            orden?: unknown[] | null;
            /** Valor Positivo */
            valor_positivo?: unknown;
            /** Grupos */
            grupos?: {
                [key: string]: unknown;
            } | null;
        };
        /** ColumnaDisposicion */
        ColumnaDisposicion: {
            /** Titulo */
            titulo: string;
            /** Variables */
            variables: string[];
        };
        /** ComparacionOptimizadores */
        ComparacionOptimizadores: {
            /** Optimizador */
            optimizador: string;
            /** Tasa Exito */
            tasa_exito: number;
            /** Costo Medio */
            costo_medio: number;
            /** Segundos Medios */
            segundos_medios: number;
        };
        /** ComparacionReferencia */
        ComparacionReferencia: {
            /** Metrica */
            metrica: string;
            /** Modelo Causal */
            modelo_causal: number;
            /** Referencia */
            referencia: number;
            /** Diferencia */
            diferencia: number;
        };
        /** CondicionesPrescripcion */
        CondicionesPrescripcion: {
            /** Problemas */
            problemas: components["schemas"]["ProblemaAplicabilidad"][];
            /** Bloqueado */
            bloqueado: boolean;
            /** Aviso */
            aviso: string;
        };
        /** ConfiguracionAccion */
        ConfiguracionAccion: {
            /** Variable */
            variable: string;
            /**
             * Permitida
             * @default true
             */
            permitida: boolean;
            /**
             * Direccion
             * @default ambas
             * @enum {string}
             */
            direccion: "subir" | "bajar" | "ambas";
            /**
             * Minimo
             * @description Límite absoluto (unidades originales).
             */
            minimo?: number | null;
            /** Maximo */
            maximo?: number | null;
            /**
             * Cambio Maximo
             * @description Cambio máximo respecto del valor actual (unidades originales).
             */
            cambio_maximo?: number | null;
            /**
             * Costo
             * @description Costo por unidad de la escala normalizada (rango de train).
             * @default 1
             */
            costo: number;
            /**
             * Estados Permitidos
             * @description Binarias, ordinales y categorías: estados a los que se puede pasar.
             */
            estados_permitidos?: unknown[] | null;
        };
        /** ConfiguracionPC */
        ConfiguracionPC: {
            /**
             * Prueba
             * @default fisherz
             * @enum {string}
             */
            prueba: "fisherz" | "mv_fisherz" | "chisq" | "kci";
            /**
             * Alpha
             * @default 0.05
             */
            alpha: number;
            /**
             * Corridas Bootstrap
             * @default 100
             */
            corridas_bootstrap: number;
            /**
             * Fraccion Submuestra
             * @default 0.8
             */
            fraccion_submuestra: number;
            /**
             * Umbral Frecuencia
             * @default 0.6
             */
            umbral_frecuencia: number;
            /** Max K */
            max_k?: number | null;
            /**
             * Semilla
             * @default 42
             */
            semilla: number;
            /** Procesos */
            procesos?: number;
            /**
             * Niveles
             * @description Grupos ordenados; nada de un nivel posterior causa uno anterior.
             */
            niveles: string[][];
            /**
             * Modificables
             * @default []
             */
            modificables: string[];
            /**
             * Orientaciones Manuales
             * @default []
             */
            orientaciones_manuales: components["schemas"]["OrientacionManual"][];
            /**
             * Punto Control Cada
             * @default 10
             */
            punto_control_cada: number;
            /**
             * Modo Ejecucion
             * @default adaptativo
             * @enum {string}
             */
            modo_ejecucion: "adaptativo" | "secuencial" | "paralelo";
            /**
             * Umbral Paralelo S
             * @default 30
             */
            umbral_paralelo_s: number;
            /**
             * Nombres Niveles
             * @description Títulos de los niveles (opcionales).
             */
            nombres_niveles?: string[] | null;
        };
        /** ConfiguracionPrescripcion */
        ConfiguracionPrescripcion: {
            /** Modificables */
            modificables: string[];
            objetivo: components["schemas"]["ObjetivoDeseado"];
            /** Acciones */
            acciones: {
                [key: string]: components["schemas"]["ConfiguracionAccion"];
            };
            /**
             * Supuestos
             * @default {}
             */
            supuestos: {
                [key: string]: components["schemas"]["Supuestos"];
            };
            /**
             * Mu
             * @default automatico
             */
            mu: "automatico" | number;
            /**
             * Optimizador
             * @default gradiente_proximal
             * @enum {string}
             */
            optimizador: "gradiente_proximal" | "genetico";
            /** Rejilla Mu */
            rejilla_mu?: number[];
            /**
             * Exito Calibracion
             * @default 0.95
             */
            exito_calibracion: number;
            /**
             * Arranques Aleatorios
             * @default 4
             */
            arranques_aleatorios: number;
            /**
             * Iteraciones Maximas
             * @default 300
             */
            iteraciones_maximas: number;
            /**
             * Tolerancia
             * @default 1e-8
             */
            tolerancia: number;
            /**
             * Tau Suavizado
             * @default 0.25
             */
            tau_suavizado: number;
            /**
             * Poblacion
             * @default 40
             */
            poblacion: number;
            /**
             * Generaciones
             * @default 60
             */
            generaciones: number;
            /**
             * Alfa Blx
             * @default 0.5
             */
            alfa_blx: number;
            /**
             * Probabilidad Mutacion
             * @default 0.2
             */
            probabilidad_mutacion: number;
            /**
             * Elite
             * @default 2
             */
            elite: number;
        };
        /** ConfiguracionSeparacion */
        ConfiguracionSeparacion: {
            /**
             * Tipo
             * @default estratificada
             * @enum {string}
             */
            tipo: "estratificada" | "temporal";
            /**
             * Proporcion Test
             * @default 0.3
             */
            proporcion_test: number;
            /**
             * Semilla
             * @default 42
             */
            semilla: number;
            /** Columna Fecha */
            columna_fecha?: string | null;
            /**
             * Corte
             * @description Fecha de corte AAAA-MM-DD (separación temporal).
             */
            corte?: string | null;
        };
        /** ContribucionPadre */
        ContribucionPadre: {
            /** Padre */
            padre: string;
            /** Contribucion */
            contribucion: number;
        };
        /** ControlVariable */
        ControlVariable: {
            /** Nombre */
            nombre: string;
            /**
             * Control
             * @enum {string}
             */
            control: "numerica" | "ordinal" | "categorica" | "grupo_one_hot";
            /** Columnas */
            columnas: string[];
            /** Categorias */
            categorias: unknown[];
            /**
             * Minimo
             * @description Mínimo de entrenamiento en unidades originales (numéricas).
             */
            minimo: number | null;
            /** Maximo */
            maximo: number | null;
            /**
             * Rol
             * @enum {string}
             */
            rol: "raiz" | "intermedia";
            /** Columnas En Modelo */
            columnas_en_modelo: string[];
        };
        /** ConversionUnidades */
        ConversionUnidades: {
            /** Columna */
            columna: string;
            /**
             * Condicion
             * @enum {string}
             */
            condicion: ">" | ">=" | "<" | "<=";
            /** Umbral */
            umbral: number;
            /**
             * Restar
             * @default 0
             */
            restar: number;
            /**
             * Multiplicar
             * @default 1
             */
            multiplicar: number;
            /**
             * Descripcion
             * @default
             */
            descripcion: string;
        };
        /** CorridaFallida */
        CorridaFallida: {
            /** Corrida */
            corrida: number;
            /** Motivo */
            motivo: string;
        };
        /** Corridas */
        Corridas: {
            /** Totales */
            totales: number;
            /** Completadas */
            completadas: number;
            /** Validas */
            validas: number;
            /** Fallidas */
            fallidas: components["schemas"]["CorridaFallida"][];
            /** Completo */
            completo: boolean;
        };
        /** CuerpoError */
        CuerpoError: {
            /** Codigo */
            codigo: string;
            /** Mensaje */
            mensaje: string;
            /** Detalles */
            detalles?: unknown;
        };
        /** DatosHoja */
        DatosHoja: {
            /** Hoja */
            hoja: string | null;
            /** Hojas */
            hojas: string[] | null;
            /** Filas */
            filas: number;
            /** Columnas */
            columnas: string[];
            /**
             * Vista Previa
             * @description Primeras 20 filas.
             */
            vista_previa: {
                [key: string]: unknown;
            }[];
        };
        /** DecisionMonotonia */
        DecisionMonotonia: {
            /** Padre */
            padre: string;
            /** Restriccion */
            restriccion: ("creciente" | "decreciente") | null;
            /**
             * Origen
             * @enum {string}
             */
            origen: "automatico" | "manual" | "no_aplica";
            /** Motivo */
            motivo: string;
        };
        /** DecisionesUsuario */
        DecisionesUsuario: {
            /**
             * Eliminar Duplicados
             * @default false
             */
            eliminar_duplicados: boolean;
            /**
             * Acciones Hallazgos
             * @default {}
             */
            acciones_hallazgos: {
                [key: string]: components["schemas"]["AccionHallazgo"];
            };
            /**
             * Columnas Excluidas
             * @default []
             */
            columnas_excluidas: string[];
            /**
             * Faltantes
             * @default {}
             */
            faltantes: {
                [key: string]: components["schemas"]["TratamientoColumna"];
            };
            /**
             * Codificaciones
             * @default {}
             */
            codificaciones: {
                [key: string]: components["schemas"]["Codificacion"];
            };
            /**
             * Conversiones
             * @default []
             */
            conversiones: components["schemas"]["ConversionUnidades"][];
            /**
             * Logaritmos
             * @default []
             */
            logaritmos: string[];
            /**
             * Normalizar
             * @default true
             */
            normalizar: boolean;
            /**
             * Columnas Fecha Disponibles
             * @default []
             */
            columnas_fecha_disponibles: string[];
            /**
             * Notas
             * @default []
             */
            notas: string[];
        };
        /** DetallesTrabajo */
        DetallesTrabajo: {
            /**
             * Modo
             * @enum {string}
             */
            modo: "midiendo" | "secuencial" | "paralelo";
            /** Procesos */
            procesos: number;
        };
        /** DiagnosticoVariable */
        DiagnosticoVariable: {
            /** Nombre */
            nombre: string;
            /** Tipo Final */
            tipo_final: string;
            /** Spearman */
            spearman: number | null;
            /** P Intervalos */
            p_intervalos: number | null;
            /** Limites Intervalos */
            limites_intervalos: number[];
            /** Valores Por Intervalo */
            valores_por_intervalo: number[];
            /** Filas Por Intervalo */
            filas_por_intervalo: number[];
            /** Medida */
            medida: string | null;
            /** Amplitud En Desviaciones */
            amplitud_en_desviaciones: number | null;
            /** Monotona */
            monotona: boolean | null;
            /** Motivo */
            motivo: string | null;
        };
        /** Distribucion */
        Distribucion: {
            /** Columna */
            columna: string;
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "categorias" | "histograma";
            /** Total */
            total: number;
            /** Faltantes */
            faltantes: number;
            /** Valores Distintos */
            valores_distintos: number;
            /**
             * Categorias
             * @description Valores más frecuentes (hasta 20) y 'otros'.
             */
            categorias: components["schemas"]["Categoria"][];
            histograma?: components["schemas"]["Histograma"] | null;
        };
        /** DistribucionObjetivo */
        DistribucionObjetivo: {
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "clases" | "continuo";
            /** Filas */
            filas: number;
            /**
             * Clases
             * @default []
             */
            clases: components["schemas"]["ClaseObjetivo"][];
            /** Media */
            media?: number | null;
            /** Mediana */
            mediana?: number | null;
            /** Minimo */
            minimo?: number | null;
            /** Maximo */
            maximo?: number | null;
        };
        /** DistribucionesObjetivo */
        DistribucionesObjetivo: {
            train: components["schemas"]["DistribucionObjetivo"];
            test: components["schemas"]["DistribucionObjetivo"];
        };
        /** EfectoParcial */
        EfectoParcial: {
            /** Padre */
            padre: string;
            /**
             * Coeficiente
             * @description Solo en mecanismos lineales (unidades preparadas).
             */
            coeficiente: number | null;
            /**
             * Signo
             * @description 1 creciente, -1 decreciente, 0 sube y baja (o plano).
             */
            signo: number;
            /**
             * X
             * @description Valores del padre en unidades originales.
             */
            x: number[];
            /**
             * Y
             * @description Efecto parcial (probabilidad o valor esperado).
             */
            y: number[];
            histograma?: components["schemas"]["HistogramaEfecto"] | null;
        };
        /** EjecucionBootstrap */
        EjecucionBootstrap: {
            /** Modo Solicitado */
            modo_solicitado: string;
            /** Modo Usado */
            modo_usado: string;
            /** Procesos */
            procesos: number;
            /** Motivo */
            motivo: string;
            /** Segundos Primera Corrida */
            segundos_primera_corrida: number | null;
            /** Segundos Segunda Corrida */
            segundos_segunda_corrida: number | null;
            /** Segundos Estimados Restantes */
            segundos_estimados_restantes: number | null;
        };
        /** EstadoPreparacion */
        EstadoPreparacion: {
            /**
             * Vigente
             * @description Si hay una preparación vigente (entonces 'resumen' es el suyo).
             */
            vigente: boolean;
            resumen: components["schemas"]["ResumenPreparacion"] | null;
            /** @description La de la receta vigente o, si no la hay, la sugerida (valor inicial del formulario). */
            separacion: components["schemas"]["ConfiguracionSeparacion"];
            /**
             * Columnas Fecha Disponibles
             * @description Fechas detectadas para la separación temporal.
             */
            columnas_fecha_disponibles: string[];
        };
        /** EvaluacionEleccion */
        EvaluacionEleccion: {
            /** Prueba */
            prueba: string;
            /** Max K */
            max_k: number | null;
            /** Advertencias */
            advertencias: components["schemas"]["AdvertenciaEleccion"][];
            /**
             * Tiempo Estimado S
             * @description Tiempo del bootstrap con esta elección, si se estimó.
             */
            tiempo_estimado_s: number | null;
        };
        /** EvaluacionMecanismo */
        EvaluacionMecanismo: {
            /** Variable */
            variable: string;
            /**
             * Rol
             * @enum {string}
             */
            rol: "intermedia" | "objetivo";
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "continua" | "binaria";
            /** Padres */
            padres: string[];
            /** Familia */
            familia: string;
            /** Nombre Familia */
            nombre_familia: string;
            /**
             * Elegido
             * @enum {string}
             */
            elegido: "simple" | "complejo";
            /**
             * Origen
             * @enum {string}
             */
            origen: "automatico" | "manual";
            /** Motivo */
            motivo: string;
            /**
             * Metrica
             * @enum {string}
             */
            metrica: "r2" | "exactitud_balanceada";
            /** Candidatos */
            candidatos: components["schemas"]["CandidatoMecanismo"][];
            /** Puntuacion Cv */
            puntuacion_cv: number;
            /** Puntuacion Test */
            puntuacion_test: number | null;
            /** Filas Train */
            filas_train: number;
            /** Filas Test */
            filas_test: number;
            /** Rescate */
            rescate: string[];
            /** Efectos */
            efectos: components["schemas"]["EfectoParcial"][];
        };
        /** EvaluacionModeloCausal */
        EvaluacionModeloCausal: {
            /** Objetivo */
            objetivo: string;
            /** Mecanismos */
            mecanismos: components["schemas"]["EvaluacionMecanismo"][];
            evaluacion_objetivo: components["schemas"]["EvaluacionObjetivo"];
            referencia: components["schemas"]["ModeloReferencia"];
        };
        /** EvaluacionObjetivo */
        EvaluacionObjetivo: {
            /** Umbral Decision */
            umbral_decision: number | null;
            /** Pesos Clase */
            pesos_clase: boolean;
            /** Cv */
            cv: {
                [key: string]: number | null;
            };
            /** Test */
            test: {
                [key: string]: number | null;
            };
            calibracion: components["schemas"]["Calibracion"] | null;
            /** Prevalencia Train */
            prevalencia_train: number | null;
        };
        /** EvaluacionPrescriptor */
        EvaluacionPrescriptor: {
            /** Casos */
            casos: number;
            /** Tasa Exito */
            tasa_exito: number;
            /** No Alcanzables */
            no_alcanzables: number;
            /** Cambio Medio */
            cambio_medio: {
                [key: string]: {
                    [key: string]: number | null;
                };
            };
            /** Porcentaje Acciones En Cero */
            porcentaje_acciones_en_cero: number;
            /** Porcentaje Requiere Revision */
            porcentaje_requiere_revision: number;
            /** Porcentaje Extrapolacion */
            porcentaje_extrapolacion: number;
            /** Sensibilidad Cambio Maximo */
            sensibilidad_cambio_maximo: {
                [key: string]: number;
            }[];
            /** Sensibilidad Mu */
            sensibilidad_mu: {
                [key: string]: number;
            }[];
            /** Comparacion Optimizadores */
            comparacion_optimizadores: components["schemas"]["ComparacionOptimizadores"][];
            /** Mcnemar */
            mcnemar: {
                [key: string]: unknown;
            };
            /** Mu */
            mu: number;
            /** Texto */
            texto: string;
        };
        /** Hallazgo */
        Hallazgo: {
            /** Tipo */
            tipo: string;
            /** Columnas Involucradas */
            columnas_involucradas: string[];
            /**
             * Severidad
             * @enum {string}
             */
            severidad: "alta" | "media" | "baja";
            /** Detalle */
            detalle: string;
            /** Evidencia */
            evidencia: {
                [key: string]: unknown;
            };
            /** Acciones Posibles */
            acciones_posibles: string[];
            /** Accion Sugerida */
            accion_sugerida: string | null;
            /** Identificador */
            identificador: string;
        };
        /** Histograma */
        Histograma: {
            /**
             * Limites
             * @description Bordes de los intervalos (uno más que los conteos).
             */
            limites: number[];
            /** Conteos */
            conteos: number[];
        };
        /** HistogramaEfecto */
        HistogramaEfecto: {
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "valores" | "histograma";
            /** Valores */
            valores?: number[] | null;
            /** Limites */
            limites?: number[] | null;
            /** Conteos */
            conteos: number[];
        };
        /** InfoVariableModelo */
        InfoVariableModelo: {
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "continua" | "binaria";
            /**
             * Rol
             * @enum {string}
             */
            rol: "raiz" | "intermedia" | "objetivo";
            /** Mediana */
            mediana: number | null;
            /** Minimo */
            minimo: number | null;
            /** Maximo */
            maximo: number | null;
            /** Faltantes Train */
            faltantes_train: number;
        };
        /** InformeEvaluacion */
        InformeEvaluacion: {
            meta: components["schemas"]["MetaEvaluacion"];
            evaluacion: components["schemas"]["EvaluacionPrescriptor"];
        };
        /** IntervencionEntrada */
        IntervencionEntrada: {
            /**
             * Variable
             * @description Ancestro del objetivo, o el nombre de una categoría one-hot.
             */
            variable: string;
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "desplazar" | "fijar";
            /**
             * Valor
             * @description Cantidad a sumar (desplazar) o valor/categoría (fijar), en unidades originales.
             */
            valor: unknown;
        };
        /** LimiteColumnas */
        LimiteColumnas: {
            /**
             * Estado
             * @enum {string}
             */
            estado: "ok" | "lento" | "bloqueado";
            /** Columnas */
            columnas: number;
            /** Mensaje */
            mensaje: string | null;
            /**
             * Columnas One Hot
             * @description Columnas que aporta cada codificación one-hot.
             */
            columnas_one_hot: {
                [key: string]: number;
            };
        };
        /** LineaResumen */
        LineaResumen: {
            /** Concepto */
            concepto: string;
            /** Detalle */
            detalle: string;
        };
        /** Matrices */
        Matrices: {
            /** Frecuencia Dirigida */
            frecuencia_dirigida: number[][];
            /** Frecuencia Sin Orientar */
            frecuencia_sin_orientar: number[][];
        };
        /** MetaEvaluacion */
        MetaEvaluacion: {
            /** Numero */
            numero: number;
            /** Casos */
            casos: number;
            /** Mu */
            mu: number;
            /** Optimizador */
            optimizador: string;
            /** Tasa Exito */
            tasa_exito: number;
            /** Huella Modelo */
            huella_modelo: string;
            /** Creado En */
            creado_en: string;
        };
        /** MetaLote */
        MetaLote: {
            /** Numero */
            numero: number;
            /**
             * Origen
             * @enum {string}
             */
            origen: "test" | "csv";
            /** Ruta Csv */
            ruta_csv: string | null;
            /** Casos */
            casos: number;
            /** Mu */
            mu: number;
            /** Optimizador */
            optimizador: string;
            /** Filas Con Problemas */
            filas_con_problemas: components["schemas"]["ProblemaFila"][];
            /** Columnas Ignoradas */
            columnas_ignoradas: string[];
            /** Huella Modelo */
            huella_modelo: string;
            /** Creado En */
            creado_en: string;
            /** Resumen */
            resumen: {
                [key: string]: number;
            };
        };
        /** MetadatosColumna */
        MetadatosColumna: {
            /** Nombre */
            nombre: string;
            /** Tipo Final */
            tipo_final: string;
            /** Transformaciones */
            transformaciones: string[];
            /** Parametros */
            parametros: {
                [key: string]: unknown;
            };
        };
        /** ModeloCausal */
        ModeloCausal: {
            modelo: components["schemas"]["ResumenModeloCausal"];
            evaluacion: components["schemas"]["EvaluacionModeloCausal"];
            /**
             * Controles
             * @description Ancestros del objetivo intervenibles (dummies agrupadas).
             */
            controles: components["schemas"]["ControlVariable"][];
            /**
             * Vigente
             * @description False si la versión actual del resultado de PC no es la del modelo.
             */
            vigente: boolean;
            /** Motivo Desactualizado */
            motivo_desactualizado: string | null;
            /** Filas Test */
            filas_test: number;
        };
        /** ModeloReferencia */
        ModeloReferencia: {
            /** Familia */
            familia: string;
            /** Variables */
            variables: string[];
            /** Umbral */
            umbral: number | null;
            /** Cv */
            cv: {
                [key: string]: number | null;
            };
            /** Test */
            test: {
                [key: string]: number | null;
            };
            /** Comparacion */
            comparacion: components["schemas"]["ComparacionReferencia"][];
            /** Principal */
            principal: string;
            /** Advertencia */
            advertencia: string | null;
        };
        /** ObjetivoDeseado */
        ObjetivoDeseado: {
            /**
             * Direccion
             * @enum {string}
             */
            direccion: "subir" | "bajar";
            /**
             * Valor
             * @description Probabilidad de la clase 1 (objetivo binario) o valor en unidades originales.
             */
            valor: number;
        };
        /** OrientacionManual */
        OrientacionManual: {
            /** Origen */
            origen: string;
            /** Destino */
            destino: string;
            /**
             * Justificacion
             * @default
             */
            justificacion: string;
        };
        /** PaginaLote */
        PaginaLote: {
            meta: components["schemas"]["MetaLote"];
            /** Total */
            total: number;
            /** Pagina */
            pagina: number;
            /** Por Pagina */
            por_pagina: number;
            /** Filas */
            filas: components["schemas"]["ResultadoPrescripcion"][];
        };
        /** ParVariables */
        ParVariables: {
            /** Variable A */
            variable_a: string;
            /** Variable B */
            variable_b: string;
            /** Frecuencia */
            frecuencia: number;
            /** Con Objetivo */
            con_objetivo: boolean;
        };
        /** PasoTraza */
        PasoTraza: {
            /** Variable */
            variable: string;
            /**
             * Causa
             * @enum {string}
             */
            causa: "intervencion" | "propagacion";
            /** Antes */
            antes: number | null;
            /** Despues */
            despues: number | null;
            /** Cambio */
            cambio: number;
            /** Por Padre */
            por_padre: components["schemas"]["ContribucionPadre"][];
        };
        /** PerfilColumna */
        PerfilColumna: {
            /** Nombre */
            nombre: string;
            /** Tipo Detectado */
            tipo_detectado: string;
            /** Faltantes */
            faltantes: number;
            /** Porcentaje Faltantes */
            porcentaje_faltantes: number;
            /** Valores Unicos */
            valores_unicos: number;
            /** Minimo */
            minimo: number | null;
            /** Maximo */
            maximo: number | null;
        };
        /** ProblemaAplicabilidad */
        ProblemaAplicabilidad: {
            /** Codigo */
            codigo: string;
            /**
             * Severidad
             * @enum {string}
             */
            severidad: "bloqueante" | "advertencia";
            /** Mensaje */
            mensaje: string;
            /**
             * Accion
             * @description Qué hacer para resolverlo.
             */
            accion: string;
            /**
             * Destino
             * @description Pantalla donde se resuelve (la interfaz lleva a ella).
             */
            destino: ("resultados" | "decisiones" | "preparacion" | "analisis" | "modelo_causal" | "prescripcion") | null;
            /** Variables */
            variables: string[];
        };
        /** ProblemaConfiguracion */
        ProblemaConfiguracion: {
            /** Campo */
            campo: string;
            /** Mensaje */
            mensaje: string;
        };
        /** ProblemaFila */
        ProblemaFila: {
            /** Fila */
            fila: number;
            /** Mensaje */
            mensaje: string;
        };
        /** ProblemaValidacion */
        ProblemaValidacion: {
            /**
             * Nivel
             * @enum {string}
             */
            nivel: "error" | "advertencia";
            /** Codigo */
            codigo: string;
            /** Mensaje */
            mensaje: string;
            /** Columnas */
            columnas: string[];
            /** Evidencia */
            evidencia: {
                [key: string]: unknown;
            };
        };
        /** Procedencia */
        Procedencia: {
            /** Archivo */
            archivo: string | null;
            /** Hoja */
            hoja: string | null;
            /** Sha256 */
            sha256: string | null;
            /** Objetivo */
            objetivo: string;
            /** Tipo Objetivo */
            tipo_objetivo: string | null;
            /** Filas Train */
            filas_train: number | null;
            /** Filas Test */
            filas_test: number | null;
            /** Decisiones */
            decisiones: components["schemas"]["LineaResumen"][];
            /** Separacion */
            separacion: components["schemas"]["LineaResumen"][];
            /** @description Configuración original de PC (pc.json de la ejecución). */
            configuracion: components["schemas"]["ConfiguracionPC"];
            /** Prueba Recomendada */
            prueba_recomendada: string | null;
        };
        /** Proyecto */
        Proyecto: {
            /** Id */
            id: string;
            /** Nombre */
            nombre: string;
            /** Archivo Original */
            archivo_original: string;
            /** Hoja */
            hoja: string | null;
            /** Sha256 */
            sha256: string;
            /** Objetivo */
            objetivo: string | null;
            /** Etapa Actual */
            etapa_actual: string | null;
            /**
             * Etapas
             * @description Estado de cada etapa realizada.
             */
            etapas: {
                [key: string]: "vigente" | "desactualizada";
            };
            /**
             * Trabajo Activo
             * @description Id del trabajo en curso, si hay uno.
             */
            trabajo_activo: string | null;
            /** @description Último trabajo del proyecto (para marcar los interrumpidos y reanudarlos). */
            ultimo_trabajo?: components["schemas"]["ResumenTrabajo"] | null;
            /** Creado En */
            creado_en: string;
            /** Actualizado En */
            actualizado_en: string;
        };
        /** ProyectoCreado */
        ProyectoCreado: {
            /** Id */
            id: string;
            /** Nombre */
            nombre: string;
            /** Archivo Original */
            archivo_original: string;
            /** Hoja */
            hoja: string | null;
            /** Sha256 */
            sha256: string;
            /** Objetivo */
            objetivo: string | null;
            /** Etapa Actual */
            etapa_actual: string | null;
            /**
             * Etapas
             * @description Estado de cada etapa realizada.
             */
            etapas: {
                [key: string]: "vigente" | "desactualizada";
            };
            /**
             * Trabajo Activo
             * @description Id del trabajo en curso, si hay uno.
             */
            trabajo_activo: string | null;
            /** @description Último trabajo del proyecto (para marcar los interrumpidos y reanudarlos). */
            ultimo_trabajo?: components["schemas"]["ResumenTrabajo"] | null;
            /** Creado En */
            creado_en: string;
            /** Actualizado En */
            actualizado_en: string;
            /**
             * Hojas
             * @description Hojas del libro (solo XLSX).
             */
            hojas: string[] | null;
            /**
             * Hoja Vista
             * @description Hoja usada para la vista previa.
             */
            hoja_vista: string | null;
            /** Filas */
            filas: number;
            /** Columnas */
            columnas: string[];
            /**
             * Vista Previa
             * @description Primeras 20 filas.
             */
            vista_previa: {
                [key: string]: unknown;
            }[];
        };
        /** PuntoCalibracion */
        PuntoCalibracion: {
            /** Probabilidad Media */
            probabilidad_media: number;
            /** Frecuencia Observada */
            frecuencia_observada: number;
            /** Filas */
            filas: number;
        };
        /** PuntoRejilla */
        PuntoRejilla: {
            /** Mu */
            mu: number;
            /** Tasa Exito */
            tasa_exito: number | null;
            /** Exitos */
            exitos: number;
            /** Evaluados */
            evaluados: number;
        };
        /** RecetaOrigen */
        RecetaOrigen: {
            /** Archivo */
            archivo: string | null;
            /** Hoja */
            hoja: string | null;
            /** Sha256 */
            sha256: string | null;
            /** Objetivo */
            objetivo: string;
            /** Tipo Objetivo */
            tipo_objetivo: string | null;
        };
        /** RecomendacionPrueba */
        RecomendacionPrueba: {
            /** Prueba */
            prueba: string;
            /** Motivo */
            motivo: string;
            /** Discretizacion */
            discretizacion: string | null;
            /** Variables No Monotonas */
            variables_no_monotonas: string[];
            /** Faltantes Restantes */
            faltantes_restantes: {
                [key: string]: number;
            };
            /** Proporcion Categoricas */
            proporcion_categoricas: number;
            /** Filas Train */
            filas_train: number;
            /** Variables */
            variables: number;
            /** Diagnosticos */
            diagnosticos: components["schemas"]["DiagnosticoVariable"][];
            /** Alternativas */
            alternativas: components["schemas"]["AlternativaPrueba"][];
            /** Limites Discretizacion */
            limites_discretizacion: {
                [key: string]: number[];
            };
            /** Tiempo Por Ejecucion S */
            tiempo_por_ejecucion_s: number | null;
            /** Tiempo Estimado Bootstrap S */
            tiempo_estimado_bootstrap_s: number | null;
            /** Estimacion Completa */
            estimacion_completa: boolean;
            /** Max K Sugerido */
            max_k_sugerido: number | null;
            /** Tiempo Estimado Bootstrap Max K S */
            tiempo_estimado_bootstrap_max_k_s: number | null;
            /** Nota Tiempo */
            nota_tiempo: string | null;
        };
        /** RespuestaConfiguracionPC */
        RespuestaConfiguracionPC: {
            configuracion: components["schemas"]["ConfiguracionPC"];
            /**
             * Guardada
             * @description False si es la plantilla sugerida (aún no guardada).
             */
            guardada: boolean;
        };
        /** RespuestaError */
        RespuestaError: {
            error: components["schemas"]["CuerpoError"];
        };
        /** RestriccionActiva */
        RestriccionActiva: {
            /** Variable */
            variable: string;
            /**
             * Restriccion
             * @enum {string}
             */
            restriccion: "limite" | "cambio_maximo" | "direccion" | "estados_permitidos";
            /** Mensaje */
            mensaje: string;
        };
        /** ResultadoContrafactual */
        ResultadoContrafactual: {
            /** Objetivo */
            objetivo: string;
            /**
             * Medida
             * @enum {string}
             */
            medida: "probabilidad" | "valor";
            /** Antes */
            antes: number;
            /** Despues */
            despues: number;
            /** Cambio */
            cambio: number;
            /** Umbral Decision */
            umbral_decision: number | null;
            /** Clase Antes */
            clase_antes: number | null;
            /** Clase Despues */
            clase_despues: number | null;
            /** Valores */
            valores: components["schemas"]["ValorContrafactual"][];
            /** Traza */
            traza: components["schemas"]["PasoTraza"][];
            /** Avisos */
            avisos: components["schemas"]["AvisoContrafactual"][];
            /** Aproximado */
            aproximado: boolean;
            /** Muestras */
            muestras: number;
            /** Extrapolacion */
            extrapolacion: boolean;
            /** Caso */
            caso: {
                [key: string]: unknown;
            };
        };
        /** ResultadoExportar */
        ResultadoExportar: {
            /** Carpeta */
            carpeta: string;
            /** Archivos */
            archivos: string[];
            /** Version */
            version: number;
        };
        /** ResultadoExportarPrescripcion */
        ResultadoExportarPrescripcion: {
            /** Carpeta */
            carpeta: string;
            /** Archivos */
            archivos: string[];
        };
        /** ResultadoLigado */
        ResultadoLigado: {
            /** Version */
            version: number | null;
            /** Sha256 */
            sha256: string | null;
        };
        /** ResultadoPC */
        ResultadoPC: {
            /** @description Configuración de la ejecución (pc.json); no cambia entre versiones. */
            configuracion: components["schemas"]["ConfiguracionPC"];
            receta: components["schemas"]["RecetaOrigen"];
            corridas: components["schemas"]["Corridas"];
            /** Tiempo S */
            tiempo_s: number;
            ejecucion: components["schemas"]["EjecucionBootstrap"] | null;
            /** Limites Discretizacion */
            limites_discretizacion: {
                [key: string]: number[];
            };
            /** Variables */
            variables: string[];
            /** Aristas */
            aristas: components["schemas"]["AristaAgregada"][];
            /** Ciclos */
            ciclos: string[][];
            caracterizacion: components["schemas"]["Caracterizacion"];
            matrices: components["schemas"]["Matrices"];
            /** Advertencias */
            advertencias: string[];
            /** @description Umbral y orientaciones manuales con que se agregó esta versión. */
            agregacion: components["schemas"]["Agregacion"];
            /**
             * Version
             * @description Versión guardada; null en una previsualización.
             */
            version: number | null;
            /**
             * Etiqueta
             * @description «Original» o «Ajustada: umbral X, original Y».
             */
            etiqueta: string;
            /**
             * Avisos
             * @description Advertencias de interpretación, calculadas por el núcleo.
             */
            avisos: components["schemas"]["AvisoResultado"][];
            /**
             * Disposicion
             * @description Columnas del grafo: una por nivel, con su título y las variables ordenadas para reducir cruces.
             */
            disposicion: components["schemas"]["ColumnaDisposicion"][];
            /**
             * Origen Candidatas
             * @description De qué lista de modificables salen las candidatas prescriptivas.
             * @enum {string}
             */
            origen_candidatas: "configuracion_pc" | "prescripcion";
            /** Nota Candidatas */
            nota_candidatas: string;
        };
        /** ResultadoPrescripcion */
        ResultadoPrescripcion: {
            /** Caso */
            caso: {
                [key: string]: unknown;
            };
            /** Objetivo */
            objetivo: string;
            /**
             * Medida
             * @enum {string}
             */
            medida: "probabilidad" | "valor";
            /**
             * Direccion
             * @enum {string}
             */
            direccion: "subir" | "bajar";
            /** Deseado */
            deseado: number;
            /** Antes */
            antes: number;
            /** Despues */
            despues: number;
            /** Alcanzado */
            alcanzado: boolean;
            /** Ya Cumple */
            ya_cumple: boolean;
            /** Falta */
            falta: number;
            /** Acciones */
            acciones: components["schemas"]["AccionPrescrita"][];
            /** Sin Cambio */
            sin_cambio: string[];
            /** Restricciones Activas */
            restricciones_activas: components["schemas"]["RestriccionActiva"][];
            /** Extrapolacion */
            extrapolacion: boolean;
            /** Aproximado */
            aproximado: boolean;
            /** Requiere Revision */
            requiere_revision: boolean;
            /** Referencia */
            referencia: {
                [key: string]: unknown;
            };
            /** Explicacion */
            explicacion: string;
            /** Costo Total */
            costo_total: number;
            /** Optimizador */
            optimizador: string;
            /** Mu */
            mu: number;
            /** Segundos */
            segundos: number;
            /** Traza */
            traza: components["schemas"]["PasoTraza"][];
            /** Valores */
            valores: components["schemas"]["ValorContrafactual"][];
            /** Avisos */
            avisos: components["schemas"]["AvisoContrafactual"][];
        };
        /** ResultadoValidacion */
        ResultadoValidacion: {
            /** Valido */
            valido: boolean;
            /** Errores */
            errores: components["schemas"]["ProblemaValidacion"][];
            /** Advertencias */
            advertencias: components["schemas"]["ProblemaValidacion"][];
        };
        /** ResumenMecanismo */
        ResumenMecanismo: {
            /** Familia */
            familia: string;
            /** Padres */
            padres: string[];
            /** Binaria */
            binaria: boolean;
            /** Seleccion */
            seleccion: {
                [key: string]: unknown;
            };
        };
        /** ResumenModeloCausal */
        ResumenModeloCausal: {
            /** Version Formato */
            version_formato: number;
            /** Objetivo */
            objetivo: string;
            /** Tipo Objetivo */
            tipo_objetivo: string | null;
            /**
             * Clase Positiva
             * @description Valores originales del objetivo que cuentan como 1.
             */
            clase_positiva: unknown[] | null;
            resultado_pc: components["schemas"]["ResultadoLigado"];
            /** Train Sha256 */
            train_sha256: string;
            /** Semilla */
            semilla: number;
            /** Configuracion */
            configuracion: {
                [key: string]: unknown;
            };
            subgrafo: components["schemas"]["SubgrafoModelo"];
            /**
             * Variables
             * @description Unidades preparadas.
             */
            variables: {
                [key: string]: components["schemas"]["InfoVariableModelo"];
            };
            /** Monotonia */
            monotonia: components["schemas"]["DecisionMonotonia"][];
            /** Umbral Decision */
            umbral_decision: number | null;
            /** Pesos Clase */
            pesos_clase: boolean;
            /** Imputadas En Modelo */
            imputadas_en_modelo: string[];
            /** Advertencias */
            advertencias: components["schemas"]["ProblemaAplicabilidad"][];
            /** Versiones */
            versiones: {
                [key: string]: string;
            };
            /** Huella */
            huella: string;
            /** Mecanismos */
            mecanismos: {
                [key: string]: components["schemas"]["ResumenMecanismo"];
            };
        };
        /** ResumenPreparacion */
        ResumenPreparacion: {
            /** Filas Train */
            filas_train: number;
            /** Filas Test */
            filas_test: number;
            /** Tipo Objetivo */
            tipo_objetivo: string | null;
            /** Columnas */
            columnas: components["schemas"]["MetadatosColumna"][];
            /**
             * Faltantes Restantes
             * @description Faltantes por columna en train.
             */
            faltantes_restantes: {
                [key: string]: number;
            };
            /**
             * Separacion
             * @description Separación aplicada (corte real, filas de cada conjunto).
             */
            separacion: {
                [key: string]: unknown;
            };
            separacion_configurada: components["schemas"]["ConfiguracionSeparacion"];
            distribucion_objetivo: components["schemas"]["DistribucionesObjetivo"];
            limite_columnas: components["schemas"]["LimiteColumnas"];
            /** Advertencias */
            advertencias: string[];
        };
        /** ResumenTrabajo */
        ResumenTrabajo: {
            /** Id */
            id: string;
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "recomendacion" | "pc" | "modelo_causal" | "calibracion_mu" | "lote_prescripcion" | "evaluacion_prescripcion";
            /**
             * Estado
             * @enum {string}
             */
            estado: "pendiente" | "en_curso" | "completado" | "cancelado" | "fallido" | "interrumpido";
            /** Completadas */
            completadas: number;
            /** Total */
            total: number | null;
            /** Mensaje */
            mensaje: string | null;
            /**
             * Reanudable
             * @description Si se puede reanudar ahora (estado y etapas lo permiten).
             */
            reanudable: boolean;
        };
        /** Revision */
        Revision: {
            /** Valido */
            valido: boolean;
            validacion: components["schemas"]["ResultadoValidacion"];
            /** Resumen */
            resumen: {
                [key: string]: unknown;
            };
            /** Hallazgos */
            hallazgos: components["schemas"]["Hallazgo"][];
            /** Perfiles Columnas */
            perfiles_columnas: components["schemas"]["PerfilColumna"][];
            /** Objetivo */
            objetivo: string | null;
            /** Informacion Objetivo */
            informacion_objetivo: {
                [key: string]: unknown;
            };
        };
        /** Salud */
        Salud: {
            /**
             * Estado
             * @constant
             */
            estado: "ok";
            /** Version Servidor */
            version_servidor: string;
            /** Version Nucleo */
            version_nucleo: string;
            /** Grupo Procesos Creado */
            grupo_procesos_creado: boolean;
        };
        /** SolicitudCasoPrescripcion */
        SolicitudCasoPrescripcion: {
            caso: components["schemas"]["CasoEntrada"];
        };
        /** SolicitudContrafactual */
        SolicitudContrafactual: {
            caso: components["schemas"]["CasoEntrada"];
            /**
             * Intervenciones
             * @default []
             */
            intervenciones: components["schemas"]["IntervencionEntrada"][];
        };
        /** SolicitudEvaluarPrueba */
        SolicitudEvaluarPrueba: {
            /**
             * Prueba
             * @enum {string}
             */
            prueba: "fisherz" | "mv_fisherz" | "chisq" | "kci";
            /** Max K */
            max_k?: number | null;
        };
        /** SolicitudExportar */
        SolicitudExportar: {
            /** Carpeta Destino */
            carpeta_destino: string;
            /**
             * Version
             * @description Versión que se exporta (por defecto, la actual).
             */
            version?: number | null;
        };
        /** SolicitudExportarPrescripcion */
        SolicitudExportarPrescripcion: {
            /** Carpeta Destino */
            carpeta_destino: string;
            /**
             * Lote
             * @description Lote cuyas prescripciones se exportan en CSV.
             */
            lote?: number | null;
            /**
             * Evaluacion
             * @description Evaluación que se incluye en el informe.
             */
            evaluacion?: number | null;
        };
        /** SolicitudLote */
        SolicitudLote: {
            /**
             * Origen
             * @enum {string}
             */
            origen: "test" | "csv";
            /**
             * Ruta Csv
             * @description CSV o XLSX con las columnas ORIGINALES del dataset (origen «csv»).
             */
            ruta_csv?: string | null;
        };
        /** SolicitudModeloCausal */
        SolicitudModeloCausal: {
            /**
             * Monotonia
             * @description Override por padre del objetivo; los demás se deciden con la recomendación de prueba.
             * @default {}
             */
            monotonia: {
                [key: string]: "creciente" | "decreciente" | "ninguna";
            };
            /**
             * Mecanismos
             * @description Override del tipo de mecanismo.
             * @default {}
             */
            mecanismos: {
                [key: string]: "simple" | "complejo";
            };
            /**
             * Pesos Clase
             * @description Pesos de clase en el objetivo (las probabilidades dejan de estar calibradas).
             * @default false
             */
            pesos_clase: boolean;
            /**
             * Umbral Parsimonia
             * @description Mejora mínima para preferir el modelo complejo.
             */
            umbral_parsimonia?: number | null;
        };
        /** SolicitudPreparar */
        SolicitudPreparar: {
            /** @description Separación en train y test; si falta, la de la receta anterior o la sugerida. */
            separacion?: components["schemas"]["ConfiguracionSeparacion"] | null;
        };
        /** SolicitudPrevisualizar */
        SolicitudPrevisualizar: {
            /**
             * Elecciones
             * @description Acción elegida por hallazgo: {identificador: acción}.
             */
            elecciones?: {
                [key: string]: string;
            };
        };
        /** SolicitudProyecto */
        SolicitudProyecto: {
            /**
             * Ruta Archivo
             * @description Ruta del CSV o XLSX del usuario (no se modifica: se copia).
             */
            ruta_archivo: string;
            /** Nombre */
            nombre?: string | null;
        };
        /** SolicitudReagregar */
        SolicitudReagregar: {
            /**
             * Umbral Frecuencia
             * @description Fracción mínima de corridas (0 < umbral <= 1; lo valida el núcleo).
             */
            umbral_frecuencia: number;
            /**
             * Orientaciones Manuales
             * @default []
             */
            orientaciones_manuales: components["schemas"]["OrientacionManual"][];
        };
        /** SolicitudRevision */
        SolicitudRevision: {
            /** Objetivo */
            objetivo: string;
            /** Hoja */
            hoja?: string | null;
        };
        /** SolicitudVersion */
        SolicitudVersion: {
            /**
             * Umbral Frecuencia
             * @description Fracción mínima de corridas (0 < umbral <= 1; lo valida el núcleo).
             */
            umbral_frecuencia: number;
            /**
             * Orientaciones Manuales
             * @default []
             */
            orientaciones_manuales: components["schemas"]["OrientacionManual"][];
            /**
             * Version Base
             * @description Versión que se estaba viendo al ajustar (informativo).
             */
            version_base?: number | null;
        };
        /** SolicitudVersionActual */
        SolicitudVersionActual: {
            /** Version */
            version: number;
        };
        /** SubgrafoModelo */
        SubgrafoModelo: {
            /** Variables */
            variables: string[];
            /** Padres */
            padres: {
                [key: string]: string[];
            };
            /** Aristas */
            aristas: string[][];
            /** Fuera */
            fuera: string[];
            /** Descendientes Objetivo */
            descendientes_objetivo: string[];
        };
        /** SubgrafoObjetivo */
        SubgrafoObjetivo: {
            /** Objetivo */
            objetivo: string;
            /**
             * Variables
             * @description Objetivo y ancestros, en orden topológico si no hay ciclos.
             */
            variables: string[];
            /** Padres */
            padres: {
                [key: string]: string[];
            };
            /** Aristas */
            aristas: string[][];
            /** Sin Orientar */
            sin_orientar: string[][];
            /** Fuera */
            fuera: string[];
        };
        /** Supuestos */
        Supuestos: {
            /**
             * Modificable Por Decision
             * @default false
             */
            modificable_por_decision: boolean;
            /**
             * Medida Antes Del Resultado
             * @default false
             */
            medida_antes_del_resultado: boolean;
            /**
             * No Define El Objetivo
             * @default false
             */
            no_define_el_objetivo: boolean;
            /** Confirmado En */
            confirmado_en?: string | null;
        };
        /** Trabajo */
        Trabajo: {
            /** Id */
            id: string;
            /** Proyecto Id */
            proyecto_id: string;
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "recomendacion" | "pc" | "modelo_causal" | "calibracion_mu" | "lote_prescripcion" | "evaluacion_prescripcion";
            /**
             * Estado
             * @enum {string}
             */
            estado: "pendiente" | "en_curso" | "completado" | "cancelado" | "fallido" | "interrumpido";
            /** Completadas */
            completadas: number;
            /** Total */
            total: number | null;
            /** Fallidas */
            fallidas: number;
            /** Segundos Transcurridos */
            segundos_transcurridos: number;
            /** Segundos Restantes Estimados */
            segundos_restantes_estimados: number | null;
            /** Mensaje */
            mensaje: string | null;
            /** Error */
            error: string | null;
            /** Parametros */
            parametros: {
                [key: string]: unknown;
            };
            /** Inicio */
            inicio: string | null;
            /** Fin */
            fin: string | null;
            /** @description Modo de ejecución del análisis en curso. */
            detalles?: components["schemas"]["DetallesTrabajo"] | null;
        };
        /** TratamientoColumna */
        TratamientoColumna: {
            /**
             * Ceros Como Faltantes
             * @default false
             */
            ceros_como_faltantes: boolean;
            /**
             * Indicador Medido
             * @default false
             */
            indicador_medido: boolean;
            /** Imputacion */
            imputacion?: ("eliminar_filas" | "mediana" | "multivariada") | null;
        };
        /** ValidacionConfiguracionPC */
        ValidacionConfiguracionPC: {
            /** Valida */
            valida: boolean;
            /** Errores */
            errores: components["schemas"]["ProblemaConfiguracion"][];
            /** Advertencias */
            advertencias: components["schemas"]["ProblemaConfiguracion"][];
        };
        /** ValidacionPrescripcion */
        ValidacionPrescripcion: {
            /** Valida */
            valida: boolean;
            /** Errores */
            errores: components["schemas"]["ProblemaConfiguracion"][];
            /** Condiciones */
            condiciones: components["schemas"]["ProblemaAplicabilidad"][];
            configuracion: components["schemas"]["ConfiguracionPrescripcion"];
        };
        /** ValorContrafactual */
        ValorContrafactual: {
            /** Variable */
            variable: string;
            /**
             * Rol
             * @enum {string}
             */
            rol: "raiz" | "intermedia" | "objetivo";
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "continua" | "binaria";
            /** Grupo */
            grupo: string | null;
            /** Antes */
            antes: unknown;
            /** Despues */
            despues: unknown;
            /** Antes Numerico */
            antes_numerico: number | null;
            /** Despues Numerico */
            despues_numerico: number | null;
            /** Cambio */
            cambio: number;
            /** Intervenida */
            intervenida: boolean;
            /** Extrapolacion */
            extrapolacion: boolean;
            /** Observado */
            observado: boolean;
        };
        /** VersionResultado */
        VersionResultado: {
            /** Version */
            version: number;
            /** Base */
            base: number | null;
            /** Umbral Frecuencia */
            umbral_frecuencia: number;
            /** Orientaciones Manuales */
            orientaciones_manuales: components["schemas"]["OrientacionManual"][];
            /** Creada En */
            creada_en: string;
            /**
             * Migrada
             * @description Resultado anterior a las versiones, completado al abrirlo por primera vez.
             */
            migrada: boolean;
            /** Etiqueta */
            etiqueta: string;
        };
        /** VersionesResultado */
        VersionesResultado: {
            /** Version Actual */
            version_actual: number;
            /** Umbral Original */
            umbral_original: number;
            /** Versiones */
            versiones: components["schemas"]["VersionResultado"][];
        };
        /** VistaConfiguracionPrescripcion */
        VistaConfiguracionPrescripcion: {
            configuracion: components["schemas"]["ConfiguracionPrescripcion"];
            /**
             * Guardada
             * @description False si es la configuración sugerida (aún no guardada).
             */
            guardada: boolean;
            /** Prescriptivas */
            prescriptivas: string[];
            /** Sin Camino */
            sin_camino: string[];
            /** Desconocidas */
            desconocidas: string[];
            /** Controles */
            controles: components["schemas"]["ControlVariable"][];
            /**
             * Variables Grafo
             * @description Variables del grafo que se pueden marcar como modificables.
             */
            variables_grafo: string[];
            /**
             * Modificables Pc
             * @description Modificables de la configuración de PC (punto de partida).
             */
            modificables_pc: string[];
            /**
             * Medida
             * @enum {string}
             */
            medida: "probabilidad" | "valor";
            /** Umbral Decision */
            umbral_decision: number | null;
            calibracion: components["schemas"]["CalibracionMu"] | null;
            /**
             * Mu Efectivo
             * @description μ que se usará (manual o calibrado); null si falta calibrar.
             */
            mu_efectivo: number | null;
            /** Aviso */
            aviso: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    salud_salud_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Salud"];
                };
            };
        };
    };
    apagar_apagar_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Apagado"];
                };
            };
        };
    };
    listar_proyectos_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proyecto"][];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    crear_proyectos_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudProyecto"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProyectoCreado"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    obtener_proyectos__proyecto_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proyecto"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    eliminar_proyectos__proyecto_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    obtener_revision_proyectos__proyecto_id__revision_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    revision_proyectos__proyecto_id__revision_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudRevision"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    datos_proyectos__proyecto_id__datos_get: {
        parameters: {
            query?: {
                /** @description Hoja (XLSX); por defecto, la del proyecto o la primera. */
                hoja?: string | null;
            };
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DatosHoja"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    distribucion_proyectos__proyecto_id__distribucion_get: {
        parameters: {
            query: {
                /** @description Nombre de la columna. */
                columna: string;
                /** @description Hoja (XLSX); por defecto, la del proyecto. */
                hoja?: string | null;
            };
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Distribucion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    previsualizar_decisiones_proyectos__proyecto_id__decisiones_previsualizar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudPrevisualizar"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionesUsuario"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    plantilla_decisiones_proyectos__proyecto_id__decisiones_plantilla_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionesUsuario"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    obtener_decisiones_proyectos__proyecto_id__decisiones_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionesUsuario"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    guardar_decisiones_proyectos__proyecto_id__decisiones_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionesUsuario"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionesUsuario"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    preparar_proyectos__proyecto_id__preparar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["SolicitudPreparar"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumenPreparacion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    estado_preparacion_proyectos__proyecto_id__preparacion_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EstadoPreparacion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    obtener_recomendacion_proyectos__proyecto_id__recomendacion_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecomendacionPrueba"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    recomendacion_proyectos__proyecto_id__recomendacion_post: {
        parameters: {
            query?: {
                /** @description Estimar el tiempo de PC (puede tardar minutos). */
                estimar_tiempo?: boolean;
            };
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    evaluar_prueba_proyectos__proyecto_id__recomendacion_evaluar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudEvaluarPrueba"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvaluacionEleccion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    plantilla_configuracion_pc_proyectos__proyecto_id__configuracion_pc_plantilla_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConfiguracionPC"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    validar_configuracion_pc_proyectos__proyecto_id__configuracion_pc_validar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfiguracionPC"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ValidacionConfiguracionPC"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    configuracion_pc_proyectos__proyecto_id__configuracion_pc_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaConfiguracionPC"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    guardar_configuracion_pc_proyectos__proyecto_id__configuracion_pc_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfiguracionPC"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaConfiguracionPC"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    pc_proyectos__proyecto_id__pc_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    resultado_proyectos__proyecto_id__resultado_get: {
        parameters: {
            query?: {
                /** @description Versión (por defecto, la actual). */
                version?: number | null;
            };
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResultadoPC"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    versiones_proyectos__proyecto_id__resultado_versiones_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionesResultado"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    guardar_version_proyectos__proyecto_id__resultado_versiones_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionesResultado"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    reagregar_proyectos__proyecto_id__resultado_reagregar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudReagregar"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResultadoPC"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    cambiar_version_actual_proyectos__proyecto_id__resultado_version_actual_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudVersionActual"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionesResultado"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    procedencia_proyectos__proyecto_id__resultado_procedencia_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Procedencia"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    archivo_proyectos__proyecto_id__archivos__nombre__get: {
        parameters: {
            query?: {
                /** @description Versión (por defecto, la actual). */
                version?: number | null;
            };
            header?: never;
            path: {
                proyecto_id: string;
                nombre: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/png": unknown;
                    "text/csv": unknown;
                    "application/json": unknown;
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    exportar_proyectos__proyecto_id__exportar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudExportar"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResultadoExportar"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    aplicabilidad_modelo_proyectos__proyecto_id__modelo_causal_aplicabilidad_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["SolicitudModeloCausal"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Aplicabilidad"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    modelo_causal_proyectos__proyecto_id__modelo_causal_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModeloCausal"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    construir_modelo_causal_proyectos__proyecto_id__modelo_causal_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["SolicitudModeloCausal"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    casos_modelo_proyectos__proyecto_id__modelo_causal_casos_get: {
        parameters: {
            query?: {
                /** @description Página (50 filas por página). */
                pagina?: number;
            };
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CasosModelo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    contrafactual_modelo_proyectos__proyecto_id__modelo_causal_contrafactual_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudContrafactual"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResultadoContrafactual"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    condiciones_proyectos__proyecto_id__prescripcion_condiciones_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ConfiguracionPrescripcion"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CondicionesPrescripcion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    configuracion_proyectos__proyecto_id__prescripcion_configuracion_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VistaConfiguracionPrescripcion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    guardar_proyectos__proyecto_id__prescripcion_configuracion_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfiguracionPrescripcion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VistaConfiguracionPrescripcion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    validar_proyectos__proyecto_id__prescripcion_configuracion_validar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfiguracionPrescripcion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ValidacionPrescripcion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    calibrar_proyectos__proyecto_id__prescripcion_calibrar_mu_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    caso_proyectos__proyecto_id__prescripcion_caso_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudCasoPrescripcion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResultadoPrescripcion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    lote_proyectos__proyecto_id__prescripcion_lote_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudLote"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    lotes_proyectos__proyecto_id__prescripcion_lotes_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetaLote"][];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    resultados_lote_proyectos__proyecto_id__prescripcion_lotes__numero__get: {
        parameters: {
            query?: {
                pagina?: number;
                /** @description alcanzado, no_alcanzable, requiere_revision o ya_cumple. */
                filtro?: string | null;
            };
            header?: never;
            path: {
                proyecto_id: string;
                numero: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginaLote"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    evaluacion_proyectos__proyecto_id__prescripcion_evaluacion_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    evaluaciones_proyectos__proyecto_id__prescripcion_evaluaciones_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetaEvaluacion"][];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    informe_evaluacion_proyectos__proyecto_id__prescripcion_evaluaciones__numero__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
                numero: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InformeEvaluacion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    exportar_proyectos__proyecto_id__prescripcion_exportar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proyecto_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SolicitudExportarPrescripcion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResultadoExportarPrescripcion"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    estado_trabajos__trabajo_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trabajo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    cancelar_trabajos__trabajo_id__cancelar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trabajo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
    reanudar_trabajos__trabajo_id__reanudar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trabajo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trabajo"];
                };
            };
            /** @description No encontrado. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Falta una etapa previa o hay un trabajo en curso. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
            /** @description Datos no válidos (detalles por campo). */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RespuestaError"];
                };
            };
        };
    };
}
