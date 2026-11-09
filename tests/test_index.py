from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src"))
from tcsa3000 import open_db,add_document,find


class ScopedIndex(TestCase):
    def test_index_search_reindex_is_idempotent_and_project_isolated(self):
        with TemporaryDirectory() as td:
            root=Path(td); source=root/"input"; workspace=root/"work"
            source.mkdir();workspace.mkdir()
            (source/"decision.md").write_text("AF-CORE Qwen9B R005 verified pass",encoding="utf-8")
            db=open_db(workspace)
            self.assertEqual(add_document(db,source,"decision.md","AF-CORE")["status"],"INDEXED")
            self.assertEqual(add_document(db,source,"decision.md","AF-CORE")["status"],"UNCHANGED")
            found=find(db,"AF-CORE","Qwen9B")
            self.assertEqual(len(found),1)
            self.assertEqual(found[0]["path"],"decision.md")
            self.assertEqual(len(find(db,"TCSA3000","Qwen9B")),0)
            db.close()
    def test_blocks_traversal_and_unsafe_extension(self):
        with TemporaryDirectory() as td:
            root=Path(td); src=root/"src";work=root/"work"
            src.mkdir();work.mkdir()
            (src/"no.exe").write_text("binary")
            db=open_db(work)
            for item in ("../escape.md","no.exe"):
                with self.subTest(item=item),self.assertRaises(ValueError):
                    add_document(db,src,item,"TCSA3000")
            db.close()

if __name__=="__main__":main(verbosity=2)
