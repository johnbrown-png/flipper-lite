"""
Script to indent the content inside the tab_learning block in flipper_lite.py
"""

def fix_indentation():
    file_path = r'c:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\flipper_lite.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the line with "# Normal learning view continues below"
    start_line = None
    for i, line in enumerate(lines):
        if "# Normal learning view continues below" in line:
            start_line = i + 1  # Start indenting from next line
            break
    
    if start_line is None:
        print("Could not find start marker")
        return
    
    # Find the end of main function (line before "if __name__")
    end_line = None
    for i, line in enumerate(lines):
        if "if __name__ ==" in line:
            end_line = i
            break
    
    if end_line is None:
        print("Could not find end marker")
        return
    
    print(f"Will indent lines {start_line + 1} to {end_line}")
    print(f"Total lines to indent: {end_line - start_line}")
    
    # Create new content with proper indentation
    new_lines = []
    for i, line in enumerate(lines):
        if start_line <= i < end_line:
            # Add 4 spaces of indentation if line is not empty
            if line.strip():
                new_lines.append('    ' + line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✓ Fixed indentation in flipper_lite.py")

if __name__ == '__main__':
    fix_indentation()
