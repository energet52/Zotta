#!/usr/bin/env python3
"""Add try/except error logging to FastAPI endpoint functions.

Handles:
- Proper import insertion (avoids multi-line import blocks)
- Docstrings kept outside try blocks
- HTTPException re-raised without logging
- db=None for endpoints without db dependency
"""
import re
import os

ROOT = "/Users/alexandernovoselov/Downloads/🤓Jupyter Scripts/Zotta"

FILES = {
    "backend/app/api/loans.py": "api.loans",
    "backend/app/api/underwriter.py": "api.underwriter",
    "backend/app/api/auth.py": "api.auth",
    "backend/app/api/payments.py": "api.payments",
    "backend/app/api/collections.py": "api.collections",
    "backend/app/api/reports.py": "api.reports",
    "backend/app/api/sector_analysis.py": "api.sector_analysis",
    "backend/app/api/conversations.py": "api.conversations",
    "backend/app/api/customers.py": "api.customers",
    "backend/app/api/gl.py": "api.gl",
    "backend/app/api/catalog.py": "api.catalog",
    "backend/app/api/admin.py": "api.admin",
    "backend/app/api/whatsapp.py": "api.whatsapp",
}


def find_import_insert_position(lines):
    """Find the correct position to insert new imports.
    
    Returns the line index AFTER the last completed import statement,
    being careful not to insert inside a multi-line import.
    """
    in_multiline = False
    last_import_end = 0
    
    for idx in range(min(80, len(lines))):
        line = lines[idx]
        stripped = line.strip()
        
        if in_multiline:
            if ')' in stripped:
                in_multiline = False
                last_import_end = idx + 1
            continue
        
        if stripped.startswith('import ') or stripped.startswith('from '):
            if '(' in stripped and ')' not in stripped:
                # Start of multi-line import
                in_multiline = True
            else:
                last_import_end = idx + 1
        elif stripped and not stripped.startswith('#') and not stripped.startswith('"""') and idx > 5:
            # Hit non-import code - stop looking
            break
    
    return last_import_end


def extract_docstring_lines(lines, body_start, func_end, body_indent):
    """Extract docstring lines from the beginning of a function body.
    
    Returns (docstring_lines, code_start_index) where code_start_index
    is the first line AFTER the docstring.
    """
    # Look for docstring at the start of the body
    first_content_idx = None
    for k in range(body_start, func_end + 1):
        s = lines[k].strip()
        if s:
            first_content_idx = k
            break
    
    if first_content_idx is None:
        return [], body_start
    
    first_line = lines[first_content_idx].strip()
    
    # Check if first content line is a docstring
    if not (first_line.startswith('"""') or first_line.startswith("'''")):
        return [], body_start
    
    q = first_line[:3]
    
    # Single-line docstring: """text"""
    if first_line.count(q) >= 2:
        return lines[body_start:first_content_idx + 1], first_content_idx + 1
    
    # Multi-line docstring: find closing triple-quote
    for k in range(first_content_idx + 1, func_end + 1):
        if q in lines[k]:
            # Include all lines from body_start through closing quote line
            return lines[body_start:k + 1], k + 1
    
    # No closing quote found (shouldn't happen) - treat as no docstring
    return [], body_start


def process_file(filepath, module):
    path = os.path.join(ROOT, filepath)
    with open(path) as f:
        lines = f.readlines()

    text = ''.join(lines)
    has_log_error = 'from app.services.error_logger import log_error' in text
    has_logging = bool(re.search(r'^import logging\s*$', text, re.MULTILINE))
    has_httpexc = 'HTTPException' in text

    # Find endpoints: @router.VERB( -> async def func(
    endpoints = []
    i = 0
    while i < len(lines):
        if re.match(r'\s*@router\.(get|post|put|patch|delete)\(', lines[i]):
            # Skip past decorators to def line
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('@'):
                j += 1
            if j >= len(lines):
                i += 1
                continue

            m = re.match(r'(\s*)(async\s+)?def\s+(\w+)\(', lines[j])
            if not m:
                i = j + 1
                continue

            func_name = m.group(3)
            is_async = bool(m.group(2))

            # Find end of signature using paren counting
            paren_depth = 0
            sig_end = j
            for k in range(j, len(lines)):
                for ch in lines[k]:
                    if ch == '(':
                        paren_depth += 1
                    elif ch == ')':
                        paren_depth -= 1
                if paren_depth == 0:
                    sig_end = k
                    break

            # Check for db param in signature
            sig = ''.join(lines[j:sig_end + 1])
            has_db = bool(re.search(r'\bdb\s*:', sig))

            # Find body start and indent
            body_start = sig_end + 1
            body_indent = None
            for k in range(body_start, min(body_start + 30, len(lines))):
                s = lines[k].strip()
                if s:
                    body_indent = len(lines[k]) - len(lines[k].lstrip())
                    break

            if body_indent is None:
                i = sig_end + 1
                continue

            # Find function end (last non-empty line at >= body_indent)
            func_end = body_start
            for k in range(body_start, len(lines)):
                s = lines[k].strip()
                if not s:
                    continue
                ind = len(lines[k]) - len(lines[k].lstrip())
                if ind < body_indent:
                    break
                func_end = k

            # Count meaningful body lines (excluding docstrings)
            meaningful = 0
            in_ds = False
            for k in range(body_start, func_end + 1):
                s = lines[k].strip()
                if not s:
                    continue
                if in_ds:
                    if '"""' in s or "'''" in s:
                        in_ds = False
                    continue
                if s.startswith('"""') or s.startswith("'''"):
                    q = s[:3]
                    if s.count(q) >= 2 and len(s) > 3:
                        continue  # single-line docstring
                    in_ds = True
                    continue
                meaningful += 1

            endpoints.append({
                'sig_end': sig_end,
                'body_start': body_start,
                'func_end': func_end,
                'func_name': func_name,
                'body_indent': body_indent,
                'has_db': has_db,
                'is_async': is_async,
                'meaningful': meaningful,
            })
            i = func_end + 1
        else:
            i += 1

    # Wrap in reverse order to maintain line numbers
    wrapped = 0
    skipped = []
    for ep in reversed(endpoints):
        if ep['meaningful'] <= 2:
            skipped.append(ep['func_name'])
            continue

        # Skip if already wrapped with log_error
        body_text = ''.join(lines[ep['body_start']:ep['func_end'] + 1])
        if 'log_error(' in body_text:
            skipped.append(f"{ep['func_name']} (already has log_error)")
            continue

        bi = ep['body_indent']
        ind = ' ' * bi
        xind = ' ' * (bi + 4)
        db_arg = 'db=db' if ep['has_db'] else 'db=None'
        await_prefix = 'await ' if ep['is_async'] else ''

        # Extract docstring lines (keep them outside try block)
        docstring_lines, code_start = extract_docstring_lines(
            lines, ep['body_start'], ep['func_end'], bi
        )
        
        # Get the code lines (after docstring)
        code_lines = lines[code_start:ep['func_end'] + 1]
        
        # Build new body: docstring + try: + indented code + except blocks
        new_body = []
        
        # Keep docstring before try
        new_body.extend(docstring_lines)
        
        # Add try block
        new_body.append(f'{ind}try:\n')
        for bl in code_lines:
            if bl.strip():
                new_body.append('    ' + bl)
            else:
                new_body.append(bl)
        new_body.append(f'{ind}except HTTPException:\n')
        new_body.append(f'{xind}raise\n')
        new_body.append(f'{ind}except Exception as e:\n')
        new_body.append(f'{xind}{await_prefix}log_error(e, {db_arg}, module="{module}", function_name="{ep["func_name"]}")\n')
        new_body.append(f'{xind}raise\n')

        lines[ep['body_start']:ep['func_end'] + 1] = new_body
        wrapped += 1

    # Add imports if needed
    if wrapped > 0:
        insert_at = find_import_insert_position(lines)

        to_add = []
        if not has_log_error:
            to_add.append('from app.services.error_logger import log_error\n')
        if not has_logging:
            to_add.append('import logging\n')
        if not has_httpexc:
            to_add.append('from fastapi import HTTPException\n')

        for imp in reversed(to_add):
            lines.insert(insert_at, imp)

    with open(path, 'w') as f:
        f.writelines(lines)

    return wrapped, len(endpoints), skipped


# Run
print("=" * 70)
print("Adding try/except error logging to FastAPI endpoints")
print("=" * 70)

summary = {}
for fp, mod in FILES.items():
    try:
        w, t, sk = process_file(fp, mod)
        summary[fp] = (w, t, sk)
        print(f"\n{fp}:")
        print(f"  Wrapped: {w} / {t} endpoints")
        if sk:
            print(f"  Skipped: {', '.join(sk)}")
    except Exception as e:
        summary[fp] = (0, 0, [])
        print(f"\nERR {fp}: {e}")
        import traceback
        traceback.print_exc()

total_wrapped = sum(v[0] for v in summary.values())
total_endpoints = sum(v[1] for v in summary.values())
print(f"\n{'=' * 70}")
print(f"TOTAL: {total_wrapped} endpoints wrapped / {total_endpoints} endpoints found")
print("=" * 70)
