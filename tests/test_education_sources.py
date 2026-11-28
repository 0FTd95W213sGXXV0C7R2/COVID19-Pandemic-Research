import http.server
import tempfile
import threading
import unittest
from pathlib import Path

from education_sources import acquire, valid
from audit_education_sources import pdf_rows
from extract_research_source import inspect


class SourcesTest(unittest.TestCase):
    def test_formats(self):
        self.assertTrue(valid('x.xlsx',b'PK\x03\x04','application/octet-stream'))
        self.assertFalse(valid('x.xlsx',b'PK\x03\x04','text/html'))
        self.assertFalse(valid('x.pdf',b'<html>','application/pdf'))
        self.assertTrue(valid('x.json',b'{"a":1}','application/json'))

    def test_local_http_cache_and_conflict(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type','text/csv')
                self.end_headers()
                self.wfile.write(b'a,b\n1,2\n')

        with tempfile.TemporaryDirectory() as tmp, http.server.HTTPServer(('localhost',0),Handler) as server:
            worker=threading.Thread(target=server.serve_forever)
            worker.start()
            try:
                cache=Path(tmp)
                sources={'a.csv':f'http://localhost:{server.server_port}/'}
                first=list(acquire(cache,sources))[0]
                self.assertEqual(first['status'],'acquired')
                self.assertTrue(list(acquire(cache,sources))[0]['cache_hit'])
                (cache/'a.csv').write_bytes(b'damaged')
                self.assertEqual(list(acquire(cache,sources))[0]['status'],'cache_conflict')
            finally:
                server.shutdown()
                worker.join()

    def test_neutral_csv_preserves_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"sample.csv"
            path.write_text("zero,blank,withheld\n0,,***\n")
            self.assertEqual(inspect(path)[1]["cells"],["0","","***"])

    def test_region_keys(self):
        lines=[f'{i} 県 1 2' for i in range(1,48)]+['計 47 94']
        self.assertEqual(len(pdf_rows(lines,2)),48)
        with self.assertRaises(ValueError):
            pdf_rows(lines+[lines[0]],2)
        with self.assertRaises(ValueError):
            pdf_rows(lines[1:],2)
