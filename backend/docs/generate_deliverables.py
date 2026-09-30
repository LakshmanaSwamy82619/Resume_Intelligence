from pathlib import Path
import textwrap

OUT = Path(__file__).parent
W, H = 960, 540
NAVY = (0.035, 0.055, 0.10)
PANEL = (0.075, 0.105, 0.17)
PANEL2 = (0.10, 0.14, 0.22)
BLUE = (0.45, 0.62, 1.0)
CYAN = (0.35, 0.83, 0.84)
WHITE = (0.92, 0.95, 1.0)
MUTED = (0.64, 0.70, 0.81)
GOLD = (0.98, 0.72, 0.36)


def pdf_escape(s):
    return s.encode('latin-1', 'replace').decode('latin-1').replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def build_pdf(path, pages):
    objs = [b'']
    def add(obj):
        objs.append(obj if isinstance(obj, bytes) else obj.encode('latin-1', 'replace'))
        return len(objs)-1
    catalog_id = add(b'')
    pages_id = add(b'')
    font_id = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    page_ids=[]
    for width,height,commands in pages:
        stream='\n'.join(commands).encode('latin-1','replace')
        content_id=add(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
        page_id=add(f'<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>')
        page_ids.append(page_id)
    objs[catalog_id]=f'<< /Type /Catalog /Pages {pages_id} 0 R >>'.encode()
    objs[pages_id]=f'<< /Type /Pages /Kids [{" ".join(f"{i} 0 R" for i in page_ids)}] /Count {len(page_ids)} >>'.encode()
    data=bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'); offsets=[0]
    for idx,obj in enumerate(objs[1:],1):
        offsets.append(len(data)); data.extend(f'{idx} 0 obj\n'.encode()); data.extend(obj); data.extend(b'\nendobj\n')
    xref=len(data); data.extend(f'xref\n0 {len(objs)}\n0000000000 65535 f \n'.encode())
    for off in offsets[1:]: data.extend(f'{off:010} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(objs)} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
    path.write_bytes(data)


def rect(cmd,x,y,w,h,color,stroke=None):
    cmd.append(f'{color[0]} {color[1]} {color[2]} rg')
    if stroke:
        cmd.append(f'{stroke[0]} {stroke[1]} {stroke[2]} RG 1 w')
    cmd.append(f'{x} {y} {w} {h} re '+('B' if stroke else 'f'))


def txt(cmd,x,y,s,size=14,color=WHITE,bold=False):
    cmd.extend([f'{color[0]} {color[1]} {color[2]} rg','BT',f'/{"F1"} {size} Tf',f'{x} {y} Td',f'({pdf_escape(s)}) Tj','ET'])


def line(cmd,x1,y1,x2,y2,color=BLUE,width=2):
    cmd.extend([f'{color[0]} {color[1]} {color[2]} RG',f'{width} w',f'{x1} {y1} m {x2} {y2} l S'])


def base(title,kicker='RESUME INTELLIGENCE | CAPSTONE'):
    c=[]; rect(c,0,0,W,H,NAVY); txt(c,48,502,kicker,10,CYAN); txt(c,48,458,title,28,WHITE)
    line(c,48,438,W-48,438,PANEL2,1)
    return c


def box(c,x,y,w,h,title,body,accent=BLUE):
    rect(c,x,y,w,h,PANEL,PANEL2); rect(c,x,y+h-5,w,5,accent)
    txt(c,x+14,y+h-29,title,15,WHITE)
    for i,row in enumerate(body): txt(c,x+14,y+h-51-18*i,row,10,MUTED)


def arrow(c,x1,y1,x2,y2,color=CYAN):
    line(c,x1,y1,x2,y2,color,2)
    # Compact right-facing arrow head
    line(c,x2-7,y2+4,x2,y2,color,2); line(c,x2-7,y2-4,x2,y2,color,2)


# One-page architecture: independently printable submission artifact.
c=base('System architecture and data flow','ARCHITECTURE | END-TO-END REQUEST PATH')
box(c,48,320,190,82,'Inputs',['Resume PDF / DOCX / TXT','Job brief file or text'],CYAN)
box(c,278,320,190,82,'Ingestion + structuring',['Parse / OCR / normalize','Chunk + embed + evidence'],BLUE)
box(c,508,320,190,82,'Persistent data',['PostgreSQL + pgvector','Candidate / resume / evidence'],GOLD)
box(c,738,320,174,82,'Recruiter workspace',['Briefs / shortlist','Evidence / compare'],CYAN)
arrow(c,238,360,278,360); arrow(c,468,360,508,360); arrow(c,698,360,738,360)
box(c,90,172,220,92,'Requirement understanding',['Mandatory / preferred','Experience + skill extraction'],GOLD)
box(c,370,172,220,92,'Hybrid retrieval',['Lexical + semantic','Metadata filtering'],BLUE)
box(c,650,172,220,92,'Rank + explain',['Rerank + matching agents','Gap / qualification / evidence'],CYAN)
arrow(c,310,218,370,218); arrow(c,590,218,650,218)
line(c,810,320,810,264,PANEL2,1); arrow(c,810,264,760,264)
box(c,160,64,250,66,'Resilience controls',['Provider chains, fallback, validation flags'],GOLD)
box(c,560,64,250,66,'Quality loop',['Human relevance + skill labels','P@K / NDCG / F1 / evidence support'],CYAN)
arrow(c,760,172,685,130); line(c,410,97,560,97,CYAN,2)
txt(c,48,24,'Each returned match retains requirement status, score details, source text, page, and validation state.',9,MUTED)
build_pdf(OUT/'architecture-diagram.pdf',[(W,H,c)])

# Seven-slide panel deck; timed for an 8-minute walkthrough and 2-minute Q&A.
pages=[]
def slide(title,kicker,bullets,side_title,side_lines,number):
    c=base(title,kicker)
    txt(c,52,405,'PANEL FLOW',9,CYAN)
    y=374
    for heading,detail in bullets:
        txt(c,52,y,heading,16,WHITE); y-=22
        for row in textwrap.wrap(detail,58): txt(c,68,y,row,11,MUTED); y-=16
        y-=14
    box(c,620,170,288,232,side_title,side_lines,CYAN)
    txt(c,48,28,f'{number:02d}  |  10-MINUTE PRESENTATION  |  DEMO + Q&A',9,MUTED)
    pages.append((W,H,c))

slide('Evidence-led candidate matching','00:00-00:40 | OPENING',[
 ('The problem','Recruiters need a shortlist they can inspect, with evidence behind every requirement.'),
 ('The product','Resume Intelligence combines hybrid retrieval, structured skill-gap analysis, and source-linked explanations.'),
 ('The guardrail','Scores support recruiter review; they are not automated hiring decisions.')], 'SAY', ['Show the login / workspace.','Explain the decision-support goal.','Set expectation: traceable matching, human decision.'],1)
slide('One pipeline from document to evidence','00:40-01:45 | ARCHITECTURE',[
 ('Prepare','Parse PDF, DOCX, or TXT; structure candidate facts; chunk and embed resume text.'),
 ('Find','Understand job requirements, retrieve candidates with lexical and semantic signals, then rerank.'),
 ('Explain','Matching, skill-gap, and qualification stages produce statuses and evidence for each result.')], 'POINT TO', ['Resume and job brief ingestion','PostgreSQL / pgvector plus evidence records','Fallback chains for unavailable AI providers','Full diagram: architecture-diagram.pdf'],2)
slide('A recruiter flow in the workspace','01:45-02:30 | SETUP',[
 ('Create a brief','Paste requirements or upload a PDF, DOCX, or TXT file.'),
 ('Choose a search','Run a Top 3 or Top 5 shortlist with a saved brief or natural-language query.'),
 ('Inspect the result','Open a candidate, compare profiles, and review matched, partial, and missing requirements.')], 'DEMO', ['Open Jobs and show upload input.','Open Search and select a brief.','Keep one known candidate for the evidence walkthrough.'],3)
slide('Live shortlist: follow one candidate','02:30-05:40 | DEMO',[
 ('Start the query','Use a prepared brief with a clear mandatory skill and experience requirement.'),
 ('Read the shortlist','Show score breakdown, candidate rank, and retrieval/fallback status.'),
 ('Verify the explanation','Open matched and partial skills; inspect quoted source text and page/source file.'),
 ('Review risk','Show missing requirements and any validation flag; explain that absent evidence is not proof of absence.')], 'DEMO CHECKPOINTS', ['Results view: top candidates','Candidate detail: evidence and page','Compare: side-by-side requirements','Mention education time is excluded from experience totals.'],4)
slide('Quality is measured against human labels','05:40-06:50 | EVALUATION',[
 ('Build ground truth','Label query/candidate relevance and optional expected skill states: matched, partial, missing.'),
 ('Run the same pipeline','Evaluation executes the live search path; unlabelled queries are reported as skipped.'),
 ('Read the metrics','Ranking: precision@K, recall@K, MRR, NDCG. Skill gaps: accuracy and per-class precision/recall/F1.'),
 ('Check grounding','Evidence claims are compared to persisted source evidence; report support rate and flagged results.')], 'BE TRANSPARENT', ['Metrics reflect only supplied labels and evaluated outputs.','No labels means no fabricated accuracy.','Use a representative labeled dataset for meaningful metrics.'],5)
slide('Tradeoffs, guardrails, and limits','06:50-07:35 | DESIGN',[
 ('Retrieval tradeoff','Hybrid lexical + semantic improves recall; reranking costs additional time and compute.'),
 ('Reliability','Provider chains fall back to local/deterministic paths; UI and API expose fallback status.'),
 ('Traceability','Store evidence links and validation notes with each result for recruiter review.'),
 ('Known limits','Gateway embedding compatibility needs confirmation; evaluate on your own consented corpus.')], 'DESIGN CHOICES', ['Recall first, then rerank a bounded pool.','Keep source evidence alongside extracted fields.','Human review stays in the loop.'],6)
slide('Close and invite questions','07:35-08:00 | HANDOFF',[
 ('Recap','The system turns resumes and role context into a ranked, evidence-linked shortlist.'),
 ('Show next','Open the architecture PDF and README setup/sample-use sections.'),
 ('Q&A','Reserve the final two minutes for panel questions.')], 'Q&A | 08:00-10:00', ['How do you evaluate match quality?','What happens when an AI provider is unavailable?','How do recruiters verify an explanation?'],7)
build_pdf(OUT/'panel-presentation.pdf',pages)

notes='''# Panel presentation speaker notes (10 minutes)\n\nThe companion `panel-presentation.pdf` is a seven-slide deck. Target 8 minutes for the walkthrough and reserve 2 minutes for Q&A.\n\n## Before the demo\n- Start backend and frontend; sign in with an HR account.\n- Confirm a prepared job brief and a candidate with source-linked evidence exist.\n- Keep the Admin evaluation page available only if a labeled dataset and completed run are ready; never imply metrics exist without labels.\n\n## Timed run of show\n\n| Time | Action |\n| --- | --- |\n| 00:00-00:40 | Explain evidence-led recruiter decision support.\n| 00:40-01:45 | Walk the architecture diagram from ingestion through retrieval, ranking, and evaluation.\n| 01:45-02:30 | Show job brief creation, including file upload, then open Search.\n| 02:30-05:40 | Run a prepared query; inspect shortlist, score/fallback status, requirement states, evidence, and compare.\n| 05:40-06:50 | Show how relevance and skill labels produce ranking/classification/grounding metrics. State the dataset size and limits accurately.\n| 06:50-07:35 | Explain hybrid retrieval, fallback behavior, traceability, and remaining provider/data limits.\n| 07:35-08:00 | Recap and invite questions.\n| 08:00-10:00 | Q&A.\n\n## Demo query template\n\nUse a role already represented in the loaded corpus. Example: `Find a Python and SQL engineer with production data-pipeline experience; prefer cloud deployment experience.` Pick a known resume and verify every example claim against the displayed source evidence. Do not quote invented scores or metrics.\n'''
(OUT/'presentation-speaker-notes.md').write_text(notes,encoding='utf-8')
print('Created architecture diagram, panel deck, and speaker notes.')
