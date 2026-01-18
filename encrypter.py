#!/usr/bin/env python3
"""
Generate SHA256 hash for lum.py auto-update verification
"""

import hashlib
from pathlib import Path

def generate_sha256(filename):
    """Generate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    
    with open(filename, "rb") as f:
        # Read file in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()

def main():
    source_file = Path("lum.py")
    hash_file = Path("lum.py.sha256")
    
    if not source_file.exists():
        print(f"❌ Error: {source_file} not found!")
        return 1
    
    print(f"🔐 Generating SHA256 hash for {source_file}...")
    
    # Generate hash
    file_hash = generate_sha256(source_file)
    
    # Write to .sha256 file (format: hash filename)
    hash_file.write_text(f"{file_hash}  {source_file.name}\n")
    
    print(f"✅ Hash generated: {file_hash}")
    print(f"📄 Saved to: {hash_file}")
    print(f"\n📤 Remember to commit both files:")
    print(f"   git add {source_file} {hash_file}")
    print(f"   git commit -m 'Update with SHA256 hash'")
    print(f"   git push")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())