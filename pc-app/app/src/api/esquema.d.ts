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
        /** ProblemaConfiguracion */
        ProblemaConfiguracion: {
            /** Campo */
            campo: string;
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
        /** ResultadoExportar */
        ResultadoExportar: {
            /** Carpeta */
            carpeta: string;
            /** Archivos */
            archivos: string[];
            /** Version */
            version: number;
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
            tipo: "recomendacion" | "pc";
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
            tipo: "recomendacion" | "pc";
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
