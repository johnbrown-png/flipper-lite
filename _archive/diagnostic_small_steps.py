"""
Diagnostic script to see what text is on the "Small steps" pages
"""

import fitz
import re

pdf_path = "WR_PDF/Year 1/Y1 Autumn Block 1 SOL Place value within 10.pdf"

doc = fitz.open(pdf_path)

print(f"PDF has {len(doc)} pages\n")

# Find Small steps pages
for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text("text")
    
    if "Small steps" in text:
        print(f"{'='*80}")
        print(f"PAGE {page_num + 1} - Contains 'Small steps'")
        print(f"{'='*80}")
        
        lines = text.split('\n')
        for i, line in enumerate(lines[:50]):  # First 50 lines
            if line.strip():
                print(f"{i:3d}: {line}")
        
        print(f"\n{'='*80}\n")

doc.close()
