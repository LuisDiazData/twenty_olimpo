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
    Returns metadata about success/fail, a list of final files to upload,
    and encryption_metadata with per-file encryption info.

    encryption_metadata format:
      { "filename.pdf": { "was_encrypted": bool, "decryption_successful": bool, "encryption_type": str } }
    encryption_type: "none" | "pdf_password" | "zip_password" | "rar_password" | "error"
    """
    final_files: List[Tuple[str, bytes]] = []
    total_received = len(attachments)
    enc_meta: Dict[str, Dict[str, Any]] = {}

    # Delay calling the LLM until we actually encounter a password-protected file.
    llm_passwords: List[str] = []
    passwords_fetched = False

    def get_pwds() -> List[str]:
        nonlocal llm_passwords, passwords_fetched
        if not passwords_fetched:
            if get_passwords_hook:
                llm_passwords = get_passwords_hook(email_body)
            passwords_fetched = True
        return llm_passwords

    for filename, data in attachments:
        if is_signature_image(filename, len(data)):
            continue

        ext = os.path.splitext(filename.lower())[1]

        try:
            if ext == '.zip':
                # Track encryption: pyzipper flag_bits & 0x1 means encrypted
                # We check by attempting extraction — extract_zip handles passwords internally
                try:
                    import pyzipper
                    import io as _io
                    with pyzipper.AESZipFile(_io.BytesIO(data)) as zf:
                        any_encrypted = any(info.flag_bits & 0x1 for info in zf.infolist() if not info.is_dir())
                except Exception:
                    any_encrypted = False

                extracted = extract_zip(data, get_pwds())
                if extracted:
                    final_files.extend(extracted)
                    enc_meta[filename] = {
                        "was_encrypted": any_encrypted,
                        "decryption_successful": True,
                        "encryption_type": "zip_password" if any_encrypted else "none",
                    }
                else:
                    final_files.append((filename, data))
                    enc_meta[filename] = {
                        "was_encrypted": any_encrypted,
                        "decryption_successful": False,
                        "encryption_type": "zip_password" if any_encrypted else "none",
                    }

            elif ext == '.rar':
                import rarfile as _rarfile
                import tempfile, os as _os
                try:
                    with tempfile.NamedTemporaryFile(suffix='.rar', delete=False) as tmp:
                        tmp.write(data)
                        tmp_path = tmp.name
                    with _rarfile.RarFile(tmp_path) as rf:
                        rar_encrypted = rf.needs_password()
                    _os.remove(tmp_path)
                except Exception:
                    rar_encrypted = False

                extracted = extract_rar(data, get_pwds())
                if extracted:
                    final_files.extend(extracted)
                    enc_meta[filename] = {
                        "was_encrypted": rar_encrypted,
                        "decryption_successful": True,
                        "encryption_type": "rar_password" if rar_encrypted else "none",
                    }
                else:
                    final_files.append((filename, data))
                    enc_meta[filename] = {
                        "was_encrypted": rar_encrypted,
                        "decryption_successful": False,
                        "encryption_type": "rar_password" if rar_encrypted else "none",
                    }

            elif ext == '.pdf':
                # Attempt open without password first to detect encryption
                try:
                    import io as _io
                    pikepdf.Pdf.open(_io.BytesIO(data))
                    # Opens fine — not encrypted
                    clean_pdf_bytes = try_decrypt_pdf(data, [])
                    final_files.append((filename, clean_pdf_bytes))
                    enc_meta[filename] = {
                        "was_encrypted": False,
                        "decryption_successful": True,
                        "encryption_type": "none",
                    }
                except pikepdf.PasswordError:
                    # Encrypted — try with LLM passwords
                    try:
                        clean_pdf_bytes = try_decrypt_pdf(data, get_pwds())
                        final_files.append((filename, clean_pdf_bytes))
                        enc_meta[filename] = {
                            "was_encrypted": True,
                            "decryption_successful": True,
                            "encryption_type": "pdf_password",
                        }
                    except ValueError:
                        # Could not decrypt — keep original
                        final_files.append((filename, data))
                        enc_meta[filename] = {
                            "was_encrypted": True,
                            "decryption_successful": False,
                            "encryption_type": "pdf_password",
                        }

            else:
                # Any other file type (doc, jpeg > 20kb, etc.)
                final_files.append((filename, data))
                enc_meta[filename] = {
                    "was_encrypted": False,
                    "decryption_successful": True,
                    "encryption_type": "none",
                }

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            # Fallback: keep original, mark as error
            final_files.append((filename, data))
            enc_meta[filename] = {
                "was_encrypted": False,
                "decryption_successful": False,
                "encryption_type": "error",
            }

    return {
        "total_received": total_received,
        "successful_files": len(final_files),
        "files_to_upload": final_files,
        "encryption_metadata": enc_meta,
    }
