import json
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cuatrimestral_supabase_manager import CuatrimestralSupabaseManager


class Response:
    def __init__(self, rows, content_range):
        self.rows = rows
        self.headers = {"Content-Range": content_range}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.rows).encode()


class FetchAllTests(unittest.TestCase):
    def test_paginas(self):
        manager = CuatrimestralSupabaseManager("https://example.invalid", "key")
        pages = [Response([{"id": i} for i in range(1000)], "0-999/1001"),
                 Response([{"id": 1000}], "1000-1000/1001")]
        with patch("urllib.request.urlopen", side_effect=pages) as open_mock:
            rows, error = manager.fetch_all("tabla", "select=*")
        self.assertIsNone(error)
        self.assertEqual(len(rows), 1001)
        for call, expected in zip(open_mock.call_args_list, ["0-999", "1000-1999"]):
            request = call.args[0]
            self.assertEqual(request.get_header("Range"), expected)
            self.assertEqual(request.get_header("Range-unit"), "items")
            self.assertEqual(request.get_header("Prefer"), "count=exact")
            self.assertEqual(call.kwargs["timeout"], 30)

    def test_rechaza_conteo_incompleto(self):
        manager = CuatrimestralSupabaseManager("https://example.invalid", "key")
        with patch("urllib.request.urlopen", return_value=Response([{"id": 1}], "0-0/2")):
            rows, error = manager.fetch_all("tabla")
        self.assertEqual(rows, [])
        self.assertIn("1 de 2", error)


class FormulaTests(unittest.TestCase):
    def test_meta_y_porcentaje(self):
        from export_consolidado_nacional import construir_hojas
        data = {name: [] for name in (
            'infoplazas', 'control_entrega_informes', 'informe_cuatrimestral_header',
            'informe_capacitaciones', 'informe_otras_actividades', 'informe_servicios',
            'resumen_demografico', 'resumen_servicios', 'resumen_tipo_usuario_genero')}
        data['infoplazas'] = [{'numero': 1, 'nombre': 'A', 'regional': 'R', 'cant_computadoras': 10}]
        data['resumen_demografico'] = [{'numero_infoplaza': 1, 'mes_numero': 5, 'total': 600}]
        row = construir_hojas(data)['Directorio Nacional'].iloc[0]
        self.assertEqual(row['Meta Cuatrimestre (PC×48×4)'], 1920)
        self.assertAlmostEqual(row['% Cumplimiento Meta 30%'], 0.09375)


def _datos(**tablas):
    from export_consolidado_nacional import TABLAS
    base = {t: [] for t in TABLAS}
    base.update(tablas)
    return base


class ConstruirHojasTests(unittest.TestCase):
    def setUp(self):
        from export_consolidado_nacional import construir_hojas, ORDEN_HOJAS
        self.construir = construir_hojas
        self.orden = ORDEN_HOJAS

    def test_orden_de_hojas(self):
        hojas = self.construir(_datos(infoplazas=[{'numero': 1, 'nombre': 'A', 'regional': 'R'}]))
        self.assertEqual(list(hojas), self.orden)

    def test_meta_cero_porcentaje_vacio(self):
        row = self.construir(_datos(infoplazas=[{'numero': 1, 'regional': 'R', 'cant_computadoras': 0}]))['Directorio Nacional'].iloc[0]
        self.assertEqual(row['Meta Cuatrimestre (PC×48×4)'], 0)
        self.assertTrue(row['% Cumplimiento Meta 30%'] is None or row['% Cumplimiento Meta 30%'] != row['% Cumplimiento Meta 30%'])

    def test_pc_encabezado_preferido_y_fallback(self):
        hojas = self.construir(_datos(
            infoplazas=[{'numero': 1, 'regional': 'R', 'cant_computadoras': 6},
                        {'numero': 2, 'regional': 'R', 'cant_computadoras': 5}],
            informe_cuatrimestral_header=[{'infoplaza_numero': 1, 'cant_computadoras': 15}]))
        d = hojas['Directorio Nacional'].set_index('Número')
        self.assertEqual(d.loc[1, 'Total PC'], 15)
        self.assertEqual(d.loc[1, 'Meta Cuatrimestre (PC×48×4)'], 15 * 192)
        self.assertEqual(d.loc[1, 'Diferencia PC (Enc - Cat)'], 9)
        self.assertEqual(d.loc[2, 'Total PC'], 5)
        self.assertTrue(pd_isna(d.loc[2, 'PC Encabezado Informe']))
        self.assertEqual(list(hojas['Diferencias PC']['Número']), [1])

    def test_cerradas_excluidas_y_listadas(self):
        hojas = self.construir(_datos(infoplazas=[
            {'numero': 1, 'regional': 'R', 'estado': 'Activa'},
            {'numero': 2, 'regional': 'R', 'estado': 'Cerrada Definitivamente'}]))
        self.assertEqual(list(hojas['Directorio Nacional']['Número']), [1])
        cer = hojas['Infoplazas Cerradas'].iloc[0]
        self.assertEqual(cer['Número'], 2)
        self.assertEqual(cer['Criterio de Cierre'], 'Estado del catálogo: Cerrada Definitivamente')

    def test_capacitaciones_y_otras_separadas_y_columnas_en_blanco(self):
        row = self.construir(_datos(
            infoplazas=[{'numero': 1, 'regional': 'R'}],
            informe_capacitaciones=[{'infoplaza_numero': 1, 'participantes': 10, 'horas': 2},
                                    {'infoplaza_numero': 1, 'participantes': 5, 'horas': 1.5}],
            informe_otras_actividades=[{'infoplaza_numero': 1, 'participantes': 7}]))['Directorio Nacional'].iloc[0]
        self.assertEqual((row['Cant. Capacitaciones'], row['Participantes Capacitaciones'], row['Horas Capacitación']), (2, 15, 3.5))
        self.assertEqual((row['Cant. Otras Actividades'], row['Participantes Otras Actividades']), (1, 7))
        self.assertNotIn('Beneficiados', row.index)
        self.assertEqual((row['Operando'], row['Firmas'], row['Fotos']), ('', '', ''))

    def test_matriz_servicios(self):
        srv = self.construir(_datos(
            infoplazas=[{'numero': 1, 'regional': 'R'}],
            informe_servicios=[
                {'infoplaza_numero': 1, 'servicio_nombre': 'Internet', 'ofrecido': True},
                {'infoplaza_numero': 1, 'servicio_nombre': 'Impresión', 'ofrecido': False},
                {'infoplaza_numero': 1, 'servicio_nombre': 'Robótica', 'ofrecido': True, 'es_personalizado': True},
                {'infoplaza_numero': 1, 'servicio_nombre': 'Ajedrez', 'ofrecido': True, 'es_personalizado': True}]))['Servicios Ofrecidos'].iloc[0]
        self.assertEqual((srv['Internet'], srv['Impresión']), ('✔', '✘'))
        self.assertEqual(srv['Total Ofrecidos'], 3)
        self.assertEqual(srv['Servicios Personalizados'], 'Robótica; Ajedrez')
        self.assertNotIn('Robótica', srv.index)

    def test_total_nacional_recalcula_porcentajes(self):
        res = self.construir(_datos(
            infoplazas=[{'numero': 1, 'regional': 'A', 'cant_computadoras': 10},
                        {'numero': 2, 'regional': 'B', 'cant_computadoras': 10}],
            control_entrega_informes=[{'infoplaza_numero': 1, 'estado': 'Entregado'},
                                      {'infoplaza_numero': 2, 'estado': 'Pendiente'}],
            resumen_demografico=[{'numero_infoplaza': 1, 'mes_numero': 5, 'total': 1920},
                                 {'numero_infoplaza': 2, 'mes_numero': 5, 'total': 0}]))['Resumen Regionales']
        tot = res[res['Regional'] == 'TOTAL NACIONAL'].iloc[0]
        self.assertAlmostEqual(tot['% Cumplimiento Entrega'], 0.5)
        self.assertAlmostEqual(tot['% Cumplimiento Meta 30%'], 1920 * 0.3 / 3840)
        self.assertEqual(tot['Visitas'], 1920)


class EscribirExcelTests(unittest.TestCase):
    def test_formato_porcentaje(self):
        import tempfile, os, openpyxl
        from export_consolidado_nacional import construir_hojas, escribir_excel
        hojas = construir_hojas(_datos(infoplazas=[{'numero': 1, 'regional': 'R', 'cant_computadoras': 10}],
                                       resumen_demografico=[{'numero_infoplaza': 1, 'mes_numero': 5, 'total': 600}]))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'x.xlsx')
            escribir_excel(hojas, path)
            wb = openpyxl.load_workbook(path)
            ws = wb['Directorio Nacional']
            col = [c.value for c in ws[1]].index('% Cumplimiento Meta 30%') + 1
            self.assertEqual(ws.cell(2, col).number_format, '0.0%')
            self.assertAlmostEqual(ws.cell(2, col).value, 0.09375)
            self.assertEqual(ws.freeze_panes, 'A2')
            wb.close()


class ObtenerDatosTests(unittest.TestCase):
    def test_error_de_paginacion_aborta(self):
        from export_consolidado_nacional import obtener_datos
        class M:
            def fetch_all(self, tabla, query=''):
                return ([], 'resumen_demografico: descargadas 1000 de 1774 filas') if tabla == 'resumen_demografico' else ([], None)
        with self.assertRaises(RuntimeError) as ctx:
            obtener_datos(M(), 2026, 2)
        self.assertIn('1000 de 1774', str(ctx.exception))

    def test_filtros_del_periodo(self):
        from export_consolidado_nacional import obtener_datos
        vistas = {}
        class M:
            def fetch_all(self, tabla, query=''):
                vistas[tabla] = query
                return [], None
        obtener_datos(M(), 2026, 2)
        self.assertIn('anio=eq.2026&cuatrimestre=eq.2', vistas['informe_capacitaciones'])
        self.assertIn('mes_numero=in.(5,6,7,8)', vistas['resumen_demografico'])


def pd_isna(v):
    import pandas as pd
    return pd.isna(v)


if __name__ == '__main__':
    unittest.main()
