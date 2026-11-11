"""Educational cloud requirements agent. No AWS permissions required."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
OUTPUT = Path('outputs')
OUTPUT.mkdir(exist_ok=True)

SYSTEM = """You are a cloud requirements analyst for a student cloud project.
Extract concrete requirements and identify dependencies and unanswered questions.
Never claim you have deployed, configured, or tested any infrastructure.
Use only these AWS services: S3, CloudFront, Route 53, ACM.
Return JSON with keys: summary (string), requirements (array of strings),
service_dependencies (array of strings), risks (array of strings),
questions (array of strings). No markdown fences."""

def save_analysis(analysis):
    """A local tool that writes a structured result for downstream agents."""
    path = OUTPUT / 'requirements.json'
    path.write_text(json.dumps({
        'created_at': datetime.now(timezone.utc).isoformat(),
        'model': MODEL, 'analysis': analysis
    }, indent=2), encoding='utf-8')
    return str(path)

def analyze(request):
    client = OpenAI()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{'role': 'system', 'content': SYSTEM},
                  {'role': 'user', 'content': request}],
        response_format={'type': 'json_object'},
        temperature=0,
    )
    raw = response.choices[0].message.content
    data = json.loads(raw)
    expected = {'summary': str, 'requirements': list,
                'service_dependencies': list, 'risks': list, 'questions': list}
    for key, kind in expected.items():
        if key not in data or not isinstance(data[key], kind):
            raise ValueError(f'Invalid agent output: {key} must be {kind.__name__}')
    return data

def main():
    request = ('Build a five-page static website with a custom domain, '
               'valid HTTPS certificate, private S3 origin, CloudFront delivery, '
               'and HTTP-to-HTTPS redirects.')
    print('Task:', request)
    for attempt in range(1, 3):
        try:
            result = analyze(request)
            print(json.dumps(result, indent=2))
            print('Saved to:', save_analysis(result))
            return
        except (ValueError, json.JSONDecodeError) as exc:
            print(f'Attempt {attempt} failed validation: {exc}')
    raise RuntimeError('Agent failed to produce valid output after two attempts')

if __name__ == '__main__':
    main()
