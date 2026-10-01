"""Preserve exact source configs in ZIP and whitespace-clean review text copies."""
import sys,json,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import EVIDENCE,ROOT,dump,digest

def main():
    comparison=json.loads((EVIDENCE/'config_comparison.json').read_text('utf-8'))
    sources={key:Path(value) for key,value in comparison['sources'].items()}
    sources['WASS_OFFICIAL_DEFAULT']=ROOT/'official_defaults/stereo_config.txt'
    records=[]
    with zipfile.ZipFile(EVIDENCE/'original_config_copies.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for label,source in sources.items():
            exact=source.read_bytes();archive.writestr(label+'.txt',exact)
            target=EVIDENCE/(label+'.txt')
            text=exact.decode('utf-8')
            target.write_text('\n'.join(line.rstrip() for line in text.splitlines()).rstrip()+'\n',encoding='utf-8')
            records.append({'label':label,'source':str(source),'exact_source_sha256':digest(source),
                'zip_member':label+'.txt','review_text':str(target),'review_text_sha256':digest(target),
                'review_text_normalization':'trailing whitespace and final empty lines only; exact original bytes retained in original_config_copies.zip'})
    dump('config_copy_provenance.json',records)
    print(json.dumps({'exact_config_files_archived':len(records)}))

if __name__=='__main__':main()
