from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paf_noise_cli.cli import extract_metrics, flatten_record, parse_detail_page, parse_list_page

LIST_HTML = """
<html>
  <body>
    <div>PAF &gt; Rumore &gt; Banca dati - macchinari: 2.452</div>
    <a href="fo_rumore_list_macchinari.php?lg=IT&page=1">1</a>
    <a href="fo_rumore_list_macchinari.php?lg=IT&page=7">7</a>
    <a href="fo_rumore_viewer_for_macchianario.php?objId=638">Scheda 638</a>
    <a href="fo_rumore_viewer_for_macchianario.php?objId=28853">Scheda 28853</a>
    <a href="fo_rumore_viewer_for_macchianario.php?objId=638">Scheda 638 duplicate</a>
  </body>
</html>
"""


DETAIL_HTML = """
<html>
  <head>
    <title>HONDA UM 616</title>
  </head>
  <body>
    <h1>Scheda Macchinario</h1>
    <div>Marca: HONDA</div>
    <div>Modello: UM 616</div>
    <div>Tipologia: Tosaerba semovente</div>
    <div>Peso: 77 kg</div>
    <div>Potenza: 4 kW</div>
    <div>Alimentazione: Motore a scoppio benzina</div>
    <div>Cilindrata: 163 cc</div>
    <div>Norma di riferimento: UNI EN ISO 22868</div>
    <div>Valori dichiarati ai sensi della norma UNI EN ISO 22868</div>
    <p>Livello pressione acustica</p>
    <table>
      <tr>
        <th>L_{Aeq}(dBA) ±K dB</th>
        <th>Potenza acustica</th>
        <th>L_{WA}(dB) ±K dB</th>
        <th>Note</th>
      </tr>
      <tr>
        <td>85 dB</td>
        <td></td>
        <td>100 dB</td>
        <td>Valore di Picco dichiarato 109 dBC</td>
      </tr>
    </table>
    <p>Questo macchinario potrebbe avere anche dei rischi derivanti da: Vibrazioni Mano-Braccio</p>
    <h3>COMPARTO: Silvicoltura ACCESSORIO: Lama LAVORO EFFETTUATO: Taglio erba</h3>
    <div>Condizioni ambiente: aperto</div>
    <div>Referente: AUSL 7 -Siena Laboratorio Agenti Fisici</div>
    <div>Stato di manutenzione: buono</div>
    <div>Lavoro effettuato: Taglio erba</div>
    <h3>Condizioni</h3>
    <div>Tipo terreno/strada: terra battuta</div>
    <div>Materiale lavorato: Erba</div>
    <div>Condizioni misura: esterno</div>
    <div>Presenza superfici riflettenti: si</div>
    <div>LIVELLO DI POTENZA ACUSTICA MISURATA Norma di riferimento: UNI EN ISO 3746</div>
    <div>L_{WA} 99 dBA ± 3.8</div>
    <h3>MISURA 10cm DALL'ORECCHIO DELL'OPERATORE</h3>
    <div>DATI MISURATI A 10 cm DALL'ORECCHIO DELL'OPERATORE L _{Aeq} (Media aritmetica)</div>
    <div>91.5 dBA L _{Ceq} (Media aritmetica) 95.4 dBC P _{peak} (Media aritmetica) 109.6 dBC</div>
    <div>SPETTRI IN OTTAVE PER CALCOLO OBM - DI UNA DELLE MISURE (a 10 cm dall'orecchio) 63 HZ 125 HZ 250 HZ 500 Hz 1000 Hz 2000 Hz 4000 Hz 8000 Hz NOTE</div>
    <div>80.9 90 87.9 86.5 82.1 82.4 77 70.4</div>
    <footer>Diritti Valori Innovazione Sostenibilita</footer>
  </body>
</html>
"""


class CliParsingTests(unittest.TestCase):
    def test_parse_list_page(self) -> None:
        info = parse_list_page(LIST_HTML)
        self.assertEqual(info.total_count, 2452)
        self.assertEqual(info.max_page, 7)
        self.assertEqual(info.obj_ids, [638, 28853])

    def test_parse_detail_page(self) -> None:
        record = parse_detail_page(
            obj_id=28853,
            url="https://example.test/fo_rumore_viewer_for_macchianario.php?objId=28853",
            html=DETAIL_HTML,
        )
        self.assertEqual(record.page_title, "HONDA UM 616")
        self.assertEqual(record.machine["brand"], "HONDA")
        self.assertEqual(record.machine_numeric["weight_kg"], 77.0)
        self.assertEqual(record.declared_values["laeq_dba"], 85.0)
        self.assertEqual(record.declared_values["lwa_dba"], 100.0)
        self.assertEqual(record.context["comparto"], "Silvicoltura")
        self.assertEqual(record.context_details["environment"], "aperto")
        self.assertEqual(record.conditions["material_processed"], "Erba")
        self.assertEqual(record.measured_power["lwa"], 99.0)
        self.assertEqual(record.measurements[0].heading, "MISURA 10cm DALL'ORECCHIO DELL'OPERATORE")
        self.assertEqual(record.measurements[0].octave_bands["63_hz"], 80.9)

    def test_extract_metrics(self) -> None:
        metrics = extract_metrics("L _{Aeq} 91.5 dBA L _{Ceq} 95.4 dBC P _{peak} 109.6 dBC")
        normalized = {(metric.metric, metric.value, metric.unit) for metric in metrics}
        self.assertIn(("L_Aeq", 91.5, "dBA"), normalized)
        self.assertIn(("L_Ceq", 95.4, "dBC"), normalized)
        self.assertIn(("P_peak", 109.6, "dBC"), normalized)

    def test_flatten_record(self) -> None:
        record = parse_detail_page(
            obj_id=28853,
            url="https://example.test/fo_rumore_viewer_for_macchianario.php?objId=28853",
            html=DETAIL_HTML,
        )
        payload = flatten_record(record)
        self.assertEqual(payload["brand"], "HONDA")
        self.assertEqual(payload["declared_laeq_dba"], 85.0)
        self.assertEqual(payload["measured_power_lwa"], 99.0)
        self.assertEqual(payload["first_measurement_laeq"], 91.5)
        json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
