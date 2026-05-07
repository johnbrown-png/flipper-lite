# White Rose PDF Curriculum Extractor - Usage Guide

## ✅ Tool Successfully Built!

The PDF curriculum extractor has been created and tested successfully. It extracts data from White Rose Education PDFs and generates CSV files with dynamic columns based on the number of small steps in each document.

## 📊 What It Produces

**Output CSV Columns:**
- Fixed metadata: `year`, `term`, `block`, `topic`, `sub_topic`
- Variable small steps: `small_step_1`, `small_step_2`, ..., `small_step_N` (N varies per PDF)
- Variable descriptions: `SS1_desc`, `SS2_desc`, ..., `SSN_desc`

**Example Output:**
```csv
year,term,block,topic,sub_topic,small_step_1,small_step_2,...,SS1_desc,SS2_desc,...
Year 1,Autumn,1,Place value,Place value within 10,Sort objects,Count objects,...,"In this small step...","The aim of this..."
Year 1,Autumn,2,Addition and subtraction,Addition and subtraction within 10,Introduce parts and wholes,...
```

## 🚀 How to Use

### Basic Usage - Process a Year Folder

```bash
python extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 1" --output "curriculum_data_hybrid.csv"
```

### Append to Existing CSV (Process Multiple Years)

```bash
# Process Year 1
python extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 1" --output "all_years.csv"

# Append Year 2
python extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 2" --output "all_years.csv" --append

# Append Year 3
python extract_pdf_curriculum_hybrid.py --folder "WR_PDF/Year 3" --output "all_years.csv" --append
```

### Skip Problematic PDFs

Some PDFs may cause the extraction to hang. You can skip them:

```bash
python extract_pdf_curriculum.py --folder "WR_PDF/Year 1" --skip "Y1 Spring Block 4 SOL Length and height.pdf" "Y1 Summer Block 1 SOL Multiplication and division.pdf"
```

### Interrupt and Save

If the script hangs on a PDF, press `Ctrl+C` to interrupt. The script will automatically save all PDFs processed up to that point.

## 📁 Folder Structure

Organize your PDFs by year for easy batch processing:

```
WR_PDF/
├── Year 1/
│   ├── Y1 Autumn Block 1 SOL Place value within 10.pdf
│   ├── Y1 Autumn Block 2 SOL Addition and subtraction within 10.pdf
│   └── ...
├── Year 2/
│   ├── Y2 Autumn Block 1 SOL...pdf
│   └── ...
└── Year 3/
    └── ...
```

## ⚠️ Known Issues & Troubleshooting

### Issue: Script Hangs on Certain PDFs

**Cause:** Some PDFs have formatting issues that cause pdfplumber to loop infinitely during parsing.

**Solutions:**
1. **Use Ctrl+C** to interrupt - the script will save what it processed
2. **Use --skip** parameter to skip problematic files
3. **Regenerate PDFs** - The original PDFs may be corrupted
4. **Try alternative PDF reader** - Consider re-saving PDFs using Adobe Acrobat or similar

**Problematic PDFs identified in Year 1:**
- Y1 Spring Block 4 SOL Length and height.pdf
- Y1 Summer Block 1 SOL Multiplication and division.pdf
- (Possibly others)

### Issue: Step count doesn't match description count

**Example:** "15 steps but 16 descriptions"

**Cause:** Some PDFs may have an extra "Notes and guidance" section that doesn't correspond to a small step.

**Impact:** Minimal - extra descriptions are included but won't cause errors. Review the CSV to verify accuracy.

### Issue: Incomplete Descriptions

Some descriptions may not be extracted perfectly due to complex PDF formatting (merged cells, overlapping text, etc.).

**Solution:** Review and manually edit the CSV if needed for critical descriptions.

## 📋 Tips for Success

1. **Test First:** Always test on a small batch (3-5 PDFs) before processing all files
2. **Backup PDFs:** Keep original PDFs in case you need to retry or fix issues
3. **Check CSV:** Open the CSV in Excel/Google Sheets to verify data quality
4. **Incremental Processing:** Process one year at a time using --append
5. **Document Skips:** Keep a list of skipped files to address later

## 🔧 Advanced Usage

### Process Only Specific PDFs

Create a custom script to process only selected PDFs:

```python
from extract_pdf_curriculum import PDFCurriculumExtractor

extractor = PDFCurriculumExtractor(output_csv="custom_output.csv")

pdfs = [
    "WR_PDF/Year 1/Y1 Autumn Block 1 SOL Place value within 10.pdf",
    "WR_PDF/Year 1/Y1 Autumn Block 2 SOL Addition and subtraction within 10.pdf"
]

for pdf_path in pdfs:
    data = extractor.process_pdf(pdf_path)
    if data:
        row = extractor.create_dynamic_row(data)
        extractor.all_data.append(row)

extractor.save_csv()
```

### Get Processing Status

The script outputs progress for each PDF:

```
📄 Processing: Y1 Autumn Block 1 SOL Place value within 10.pdf
   ✓ Found 15 small steps
   ✓ Found 16 descriptions
   ⚠️  Warning: 15 steps but 16 descriptions
```

## 📊 Test Results

**Successfully Processed (Year 1):**
- ✅ Y1 Autumn Block 1 - Place value (15 steps)
- ✅ Y1 Autumn Block 2 - Addition and subtraction (17 steps)
- ✅ Y1 Autumn Block 3 - Shape (5 steps)
- ✅ Y1 Spring Block 1 - Place value within 20 (12 steps)
- ✅ Y1 Spring Block 2 - Addition and subtraction within 20 (9 steps)

**CSV Output:**
- Rows: 5
- Columns: 39 (5 fixed + 17 small_step + 17 SS_desc)
- Max steps in any block: 17

## 🎯 Next Steps

1. **Identify problematic PDFs** by running on full Year 1 folder with interrupt handling
2. **Process Year 2 and Year 3** using the --append flag
3. **Review and clean** the combined CSV for any data quality issues
4. **Handle skipped PDFs** - regenerate or manually extract data

## 📞 Support

For issues or questions:
- Check the console output for specific error messages
- Review skipped files list
- Verify PDF file integrity (try opening in PDF reader)
- Consider re-exporting problematic PDFs from original source

---

**Tool Location:** `extract_pdf_curriculum.py`
**Test Script:** `test_extraction.py`
**Sample Output:** `Year_1_curriculum.csv`
