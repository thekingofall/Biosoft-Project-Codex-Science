import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from figure_tools import scoped,plot_table
class FigureTests(unittest.TestCase):
 def setUp(self):
  parent=os.environ.get('CODEX_SCIENCE_TEST_TMP')
  if parent: Path(parent).mkdir(parents=True,exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=parent); self.root=Path(self.tmp.name)
  (self.root/'data.csv').write_text('x,y,group\n1,2,A\n2,3,A\n1,4,B\n2,5,B\n')
 def tearDown(self): self.tmp.cleanup()
 def test_path_escape(self):
  with self.assertRaises(ValueError): scoped(str(self.root),'../outside.png')
 def test_missing_category_rejected(self):
  (self.root/'missing.csv').write_text('x,y\n,2\n')
  with self.assertRaises(ValueError): plot_table(str(self.root),'missing.csv','figure','bar','x','y')
 def test_workspace_root_output_rejected(self):
  with self.assertRaises(ValueError): plot_table(str(self.root),'data.csv','.','scatter','x','y')
 def test_preserve_existing(self):
  (self.root/'figure.pdf').write_bytes(b'original')
  with self.assertRaises(FileExistsError): plot_table(str(self.root),'data.csv','figure','scatter','x','y')
  self.assertEqual((self.root/'figure.pdf').read_bytes(),b'original')
 def test_ambiguous_bar(self):
  with self.assertRaisesRegex(ValueError,'aggregate'): plot_table(str(self.root),'data.csv','figure','bar','x','y')
 @unittest.skipUnless(os.environ.get('CODEX_SCIENCE_TEST_R')=='1','R acceptance is opt-in')
 def test_real_r_plot(self):
  out=plot_table(str(self.root),'data.csv','figure','scatter','x','y','group')
  self.assertTrue(Path(out['files']['pdf']).read_bytes().startswith(b'%PDF'))
  self.assertTrue(Path(out['files']['png']).read_bytes().startswith(b'\x89PNG'))
 @unittest.skipUnless(os.environ.get('CODEX_SCIENCE_TEST_R')=='1','R acceptance is opt-in')
 def test_r_preserves_category_identifiers(self):
  (self.root/'categories.csv').write_text('x,y\n01,2\n1,5\n')
  out=plot_table(str(self.root),'categories.csv','bar','bar','x','y')
  import pypdfium2
  with pypdfium2.PdfDocument(out['files']['pdf']) as doc:
   page=doc[0]; text=page.get_textpage(); actual=text.get_text_range(); text.close(); page.close()
  self.assertIn('01',actual)
if __name__=='__main__': unittest.main()
