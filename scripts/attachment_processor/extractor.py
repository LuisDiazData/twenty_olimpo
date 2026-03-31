import io
import os
import pikepdf
import pyzipper
import rarfile
from typing import List, Tuple, Dict, Any

# Threshold to ignore signatures (in bytes), e.g., 20 KB
SIGNATURE_SIZE_LIMIT = 20 * 1024
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

def is_signature_image(filename: str, size: int) -> bool:
    """Returns True if the file looks like a small signature image."""
    ext = os.path.splitext(filename.lower())[1]
    if ext in IMAGE_EXTENSIONS and size < SIGNATURE_SIZE_LIMIT:
        return True
    return False

def try_decrypt_pdf(file_bytes: bytes, passwords: List[str]) -> bytes:
    """
    Attempts to open a PDF. If encrypted, tries the passwords.
    Returns the unencrypted PDF bytes if successful, else raises ValueError.
    """
    try:
        # Try without password first
        pdf = pikepdf.Pdf.open(io.BytesIO(file_bytes))
        out_stream = io.BytesIO()
        pdf.save(out_stream)
        return out_stream.getvalue()
    except pikepdf.PasswordError:
        # Needs password
        for pwd in passwords:
            try:
                pdf = pikepdf.Pdf.open(io.BytesIO(file_bytes), password=pwd)
                out_stream = io.BytesIO()
                pdf.save(out_stream)
                return out_stream.getvalue()
            except pikepdf.PasswordError:
                continue
        raise ValueError("No valid password found for PDF.")

def extract_zip(file_bytes: bytes, passwords: List[str]) -> List[Tuple[str, bytes]]:
    """
    Extracts files from a ZIP archive. Tries passwords if encrypted.
    Filters out signatures from the extracted files.
    """
    extracted_files = []
    with pyzipper.AESZipFile(io.BytesIO(file_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            
            # If the file seems to be encrypted
            file_data = None
            if info.flag_bits & 0x1:
                # Try passwords
                for pwd in passwords:
                    try:
                        file_data = zf.read(info.filename, pwd=pwd.encode('utf-8'))
                        break
                    except (RuntimeError, pyzipper.zipfile.BadZipFile):
                        continue
                if file_data is None:
                    # Failed to decrypt this specific file
                    print(f"Failed to decrypt ZIP item: {info.filename}")
                    continue
            else:
                file_data = zf.read(info.filename)
            
            if file_data:
                # Check for signature inside zip
                if not is_signature_image(info.filename, len(file_data)):
                    extracted_files.append((os.path.basename(info.filename), file_data))

    return extracted_files

def extract_rar(file_bytes: bytes, passwords: List[str]) -> List[Tuple[str, bytes]]:
    """
    Extracts files from a RAR archive. Tries passwords if encrypted.
    """
    extracted_files = []
    # rarfile needs a physical file or unrar command installed, 
    # but with modern rarfile it can parse some from memory or temp files.
    # For robust handling, write to a temp file.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.rar', delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        with rarfile.RarFile(tmp_path) as rf:
            for info in rf.infolist():
                if info.isdir():
                    continue
                
                if rf.needs_password():
                    file_data = None
                    for pwd in passwords:
                        rf.setpassword(pwd)
                        try:
                            file_data = rf.read(info.filename)
                            break
                        except rarfile.BadRarFile:
                            continue
                    if file_data is None:
                        print(f"Failed to decrypt RAR item: {info.filename}")
                        continue
                else:
                    file_data = rf.read(info.filename)
                
                if file_data:
                    if not is_signature_image(info.filename, len(file_data)):
                        extracted_files.append((os.path.basename(info.filename), file_data))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return extracted_files

def process_attachments(attachments: List[Tuple[str, bytes]], email_body: str, get_passwords_hook=None) -> Dict[str, Any]:
    """
    Main entrypoint for processing attachments.
    Returns metadata about success/fail, and a list of final files to upload.
    """
    final_files = [] # list of (filename, bytes)
    total_received = len(attachments)
    
    # We delay calling the LLM until we actually encounter a password-protected file
    # to save costs and time.
    llm_passwords = []
    passwords_fetched = False

    def get_pwds():
        nonlocal llm_passwords, passwords_fetched
        if not passwords_fetched:
            if get_passwords_hook:
                llm_passwords = get_passwords_hook(email_body)
            passwords_fetched = True
        return llm_passwords

    for filename, data in attachments:
        if is_signature_image(filename, len(data)):
            # Skip signatures
            continue
            
        ext = os.path.splitext(filename.lower())[1]
        
        try:
            if ext == '.zip':
                extracted = extract_zip(data, get_pwds())
                if extracted:
                    final_files.extend(extracted)
                else:
                    # Si no se pudo extraer nada (posiblemente por contraseña errónea), guarda el zip original
                    final_files.append((filename, data))
            elif ext == '.rar':
                extracted = extract_rar(data, get_pwds())
                if extracted:
                    final_files.extend(extracted)
                else:
                    # Si no se pudo extraer nada, guarda el rar original
                    final_files.append((filename, data))
            elif ext == '.pdf':
                clean_pdf_bytes = try_decrypt_pdf(data, get_pwds())
                final_files.append((filename, clean_pdf_bytes))
            else:
                # Any other file type (doc, jpeg > 20kb, etc.) gets passed along as is
                final_files.append((filename, data))
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            # RESPALDO: Si no logramos desencriptar o hubo cualquier otro error, guardamos el original
            final_files.append((filename, data))

    return {
        "total_received": total_received,
        "successful_files": len(final_files),
        "files_to_upload": final_files
    }
