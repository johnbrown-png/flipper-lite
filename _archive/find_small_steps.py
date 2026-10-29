import pdfplumber
import os
import re

pdf_paths = [
    r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\WR_PDF\Y1 Autumn Block 2 SOL Addition and subtraction within 10.pdf",
    r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\WR_PDF\Y1 Autumn Block 3 SOL Shape.pdf"
]

for pdf_path in pdf_paths:
    if not os.path.exists(pdf_path):
        print(f"\nFILE NOT FOUND: {pdf_path}\n")
        continue
        
    print("\n" + "="*80)
    print(f"PDF: {os.path.basename(pdf_path)}")
    print("="*80)
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total Pages: {len(pdf.pages)}")
        
        # Search for "Small steps" page
        small_steps_pages = []
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text and "Small steps" in text:
                small_steps_pages.append(i)
        
        print(f"\nPages with 'Small steps': {small_steps_pages}")
        
        # Show the small steps pages
        for page_num in small_steps_pages[:3]:  # First 3 occurrences
            page = pdf.pages[page_num - 1]
            print(f"\n--- PAGE {page_num} ---")
            print("-"*80)
            
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                print(f"Total lines: {len(lines)}\n")
                
                for i, line in enumerate(lines, 1):
                    print(f"{i:3d}: {line}")
            
            print("-"*80)
        
        # Also find first page with "Notes and guidance"
        print("\n" + "="*80)
        print("SEARCHING FOR FIRST 'Notes and guidance' PAGE")
        print("="*80)
        
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text and "Notes and guidance" in text:
                print(f"\nFirst 'Notes and guidance' found on PAGE {i}")
                print("-"*80)
                lines = text.split('\n')
                
                # Find the line with "Notes and guidance" and extract paragraph
                for line_idx, line in enumerate(lines):
                    if "Notes and guidance" in line:
                        print(f"\nLine {line_idx + 1}: {line}")
                        print("\nNext 10 lines (potential description):")
                        for j in range(line_idx + 1, min(line_idx + 11, len(lines))):
                            print(f"{j + 1:3d}: {lines[j]}")
                        break
                break
        
        print("\n" + "="*80)
