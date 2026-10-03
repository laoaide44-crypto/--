from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from datetime import date
import shutil

base = Path(__file__).parent
out = base / 'dist'
out.mkdir(exist_ok=True)
name = 'AI软件赛道 - 交付契约台 - EDG'
stage = base / '_submission_stage'
root = stage / name
zip_path = out / f'{name}.zip'
if stage.exists(): shutil.rmtree(stage)
(root / '程序').mkdir(parents=True)
(root / '文档').mkdir(parents=True)
allowed = {'.py', '.json', '.md', '.cmd', '.ps1', '.toml', '.example', '.pptx'}
skip = {'打包交付.ps1', 'make_submission_package.py', 'make_pitch.py', 'make_pitch_beautified.py',
        'pitch-check.json', 'pitch-beautified-check.json',
        'AI软件赛道 - 交付契约台 - EDG - 路演PPT.pptx'}
for p in base.iterdir():
    if p.is_file() and p.suffix in allowed and p.suffix != '.pptx' and not p.name.startswith(('app.py.bak', '~$')) and p.name not in skip:
        shutil.copy2(p, root / '程序' / p.name)
# 路演 PPT 与演示视频放在包根目录，方便评委直接找到
shutil.copy2(base / 'AI软件赛道 - 交付契约台 - EDG - 路演PPT美化版.pptx', root / 'AI软件赛道 - 交付契约台 - EDG - 路演PPT.pptx')
videos = base / '演示视频'
if videos.is_dir():
    (root / '演示视频').mkdir()
    for p in videos.iterdir():
        if p.is_file() and p.suffix.lower() in {'.mp4', '.webm', '.md'}:
            shutil.copy2(p, root / '演示视频' / p.name)
(root / '程序' / '.streamlit').mkdir()
shutil.copy2(base / '.streamlit' / 'config.toml', root / '程序' / '.streamlit' / 'config.toml')
shutil.copy2(base / 'requirements.txt', root / '程序' / 'requirements.txt')
shutil.copy2(base / '群聊摘要.txt', root / '程序' / '群聊摘要.txt')
cap = next((p for p in base.iterdir() if p.is_dir() and (p / 'samples').is_dir() and any((p/'samples').glob('SYNTHETIC_*.csv'))), None)
if cap:
    pack = root / '程序' / '现场新增能力准备包'
    (pack / 'samples').mkdir(parents=True)
    for p in cap.glob('*.md'): shutil.copy2(p, pack / p.name)
    for p in (cap / 'samples').iterdir():
        if p.name == 'README.md' or p.name.startswith('SYNTHETIC_'): shutil.copy2(p, pack / 'samples' / p.name)
for p in base.glob('*.md'):
    if not p.name.endswith('.bak-20261001-物流版'): shutil.copy2(p, root / '文档' / p.name)
files = sorted(p for p in root.rglob('*') if p.is_file())
manifest = root / 'PACKAGE_MANIFEST.txt'
manifest.write_text('\n'.join([
    'XiHack 2026 final submission package', f'Generated: {date.today().isoformat()}',
    f'File count before manifest: {len(files)}',
    'Primary scenario: fast-delivery logistics. Catering is comparison scenario.',
    'Demo video: 演示视频/ (raw silent screen recording + aligned voiceover script; replace with final edited MP4 when ready).',
    '', 'Files:', *[str(p.relative_to(root)) for p in files]
]), encoding='utf-8')
if zip_path.exists(): zip_path.unlink()
with ZipFile(zip_path, 'w', ZIP_DEFLATED) as z:
    for p in sorted(root.rglob('*')):
        if p.is_file(): z.write(p, Path(name) / p.relative_to(root))
with ZipFile(zip_path) as z:
    names = z.namelist()
    bad = [n for n in names if n.endswith('.env.local') or '.env.local/' in n or '__pycache__' in n or n.endswith('.pyc') or 'app.py.bak' in n or '_freeze-' in n]
    if bad: raise SystemExit('forbidden: ' + repr(bad))
print(zip_path)
print(f'entries={len(names)} size={zip_path.stat().st_size}')
