# Check for duplicate/overlapping classes in jobs.py 
with open('omegaml/notebook/jobs.py', 'r') as f:
    content = f.read()

# Find ALL exception class entries (there may be multiple from multi-edits)
exception_entries = [e.strip() for e in content.split('class JobAlreadyExecuted') if len(e.strip()) > 0]
print(f"Found {len(exception_entries)} JobAlreadyExecuted definitions:")
for i, entry in enumerate(exception_entries[:3]):
    first_line = entry.split('\n')[0][:50]
    print(f"\n--- Entry {i+1} ---")  
    print(first_line)

# Check if imports section is valid  
import_block = content[:content.find('class NotebookBackend')]
try:
    compile(import_block, '<imports>', 'exec')
    print("\n✓ Imports section compiles! ✓\n")
except SyntaxError as e:
    import traceback
    print(f"\n✗ Import syntax error at line {e.lineno}:")  
    print(traceback.print_exc())
    
