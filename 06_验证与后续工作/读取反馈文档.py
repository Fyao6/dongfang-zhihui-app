"""将本轮反馈的原件、图片和图文顺序保存在现有项目目录内。"""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parent.parent
reference = root / "02_需求与设计参考"
checks = root / "06_验证与后续工作"
source = Path(r"C:\Users\YIT\xwechat_files\wxid_e5ujzg7atfqp12_1b53\msg\file\2026-10\1016问题反馈.docx")
extra = Path(r"C:\Users\YIT\AppData\Local\Temp\codex-clipboard-e2712731-44de-4221-b130-ad3f03b5445b.png")

def retain(src, dst):
    if dst.exists() and dst.read_bytes() != src.read_bytes():
        raise RuntimeError(f"已有不同内容的文件，需要先核对：{dst}")
    if not dst.exists():
        shutil.copy2(src, dst)
    return hashlib.sha256(dst.read_bytes()).hexdigest()

local_doc = reference / "1016问题反馈.docx"
local_extra = reference / "首页收尾范围-用户补充.png"
doc_hash = retain(source, local_doc)
extra_hash = retain(extra, local_extra)
ns = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
with zipfile.ZipFile(local_doc) as archive:
    rels = {item.get("Id"): item.get("Target") for item in ET.fromstring(archive.read("word/_rels/document.xml.rels"))}
    document = ET.fromstring(archive.read("word/document.xml"))
    image_map = {}
    media = []
    for index, member in enumerate((name for name in archive.namelist() if name.startswith("word/media/") and not name.endswith("/")), 1):
        name = f"1016反馈-图{index:02d}{Path(member).suffix}"
        destination = reference / "用户参考图" / name
        contents = archive.read(member)
        destination.write_bytes(contents)
        image_map[member.removeprefix("word/")] = str(destination.relative_to(root)).replace("\\", "/")
        media.append({"number": index, "archive_member": member, "path": image_map[member.removeprefix("word/")], "sha256": hashlib.sha256(contents).hexdigest()})
    paragraphs = []
    for index, block in enumerate(document.find("w:body", ns)):
        text = "".join(node.text or "" for node in block.iter(f"{{{ns['w']}}}t"))
        images = []
        for blip in block.iter(f"{{{ns['a']}}}blip"):
            target = rels.get(blip.get(f"{{{ns['r']}}}embed"))
            images.append(image_map.get(target, target))
        if text or images:
            paragraphs.append({"body_block_index": index, "text": text, "images": images})
    comments = [name for name in archive.namelist() if name.startswith("word/comments") and name.endswith(".xml")]
    result = {"document": str(local_doc.relative_to(root)).replace("\\", "/"), "sha256": doc_hash,
              "supplement_image": str(local_extra.relative_to(root)).replace("\\", "/"), "supplement_sha256": extra_hash,
              "media": media, "ordered_paragraphs": paragraphs, "comments_parts": comments,
              "tracked_insertions": len(list(document.iter(f"{{{ns['w']}}}ins"))),
              "tracked_deletions": len(list(document.iter(f"{{{ns['w']}}}del")))}

(checks / "1016反馈逐项原文.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
