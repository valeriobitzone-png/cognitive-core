"""Import Markdown notes read-only into Cognitive Vault; does not modify source."""
from pathlib import Path


def ingest_markdown_tree(vault,folder,max_files=1000):
    root=Path(folder).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('not a directory')
    imported=0
    skipped=0
    for path in root.rglob('*.md'):
        if imported>=max_files:
            break
        if '.obsidian' in path.parts or path.is_symlink():
            skipped+=1;continue
        resolved=path.resolve()
        if not resolved.is_relative_to(root):
            skipped+=1;continue
        if path.stat().st_size>vault.settings.max_text_bytes:
            skipped+=1;continue
        try:
            text=path.read_text(encoding='utf-8')
        except UnicodeError:
            skipped+=1;continue
        vault.document(path.stem,text,source_url='file:'+str(path.relative_to(root)),kind='markdown')
        imported+=1
    return {'indexed':imported,'skipped':skipped}
