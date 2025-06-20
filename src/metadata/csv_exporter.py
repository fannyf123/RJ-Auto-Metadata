# RJ Auto Metadata
# Copyright (C) 2025 Riiicil
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# src/metadata/csv_exporter.py
import os
import re
from src.utils.logging import log_message
from src.utils.file_utils import sanitize_csv_field, write_to_csv
from src.metadata.categories.for_adobestock import map_to_adobe_stock_category
from src.metadata.categories.for_shutterstock import map_to_shutterstock_category

def smart_truncate_description(description, max_length=200):
    """
    Smart truncation untuk description dengan logika:
    1. Jika <= max_length karakter: langsung return
    2a. Jika > max_length dan ada titik dalam batas: potong sampai titik terakhir
    2b. Jika > max_length tanpa titik dalam batas: hard cut ke (max_length-1) + titik
    
    Args:
        description: String description yang akan di-truncate
        max_length: Maximum karakter yang diizinkan (default: 200)
    
    Returns:
        String: Description yang sudah di-truncate dengan smart logic
    """
    if not description:
        return ""
    
    description = str(description).strip()
    
    # Langkah 1: Kalau <= max_length, aman langsung pakai
    if len(description) <= max_length:
        return description
    
    # Langkah 2: Kalau > max_length, coba smart truncation
    truncated = description[:max_length]
    
    # Cari titik terakhir dalam batas max_length
    last_period_pos = truncated.rfind('.')
    
    # Langkah 2a: Kalau ada titik dalam batas dan tidak di posisi terakhir
    # (untuk hindari kasus kaya "Lorem ipsum." yang titiknya pas di ujung)
    if last_period_pos > 0 and last_period_pos < max_length - 1:
        # Ada titik yang bagus, potong sampai titik terakhir + 1 (include titiknya)
        result = description[:last_period_pos + 1]
        log_message(f"  Smart truncate: Potong sampai titik terakhir ({len(result)} chars)")
        return result
    
    # Langkah 2b: Tidak ada titik yang cocok, hard truncate + tambah titik
    result = description[:max_length - 1] + '.'
    log_message(f"  Smart truncate: Hard cut + titik ({len(result)} chars)")
    return result

def smart_truncate_title(title, max_length=200):
    """
    Smart truncation untuk title (sama seperti description tapi untuk title)
    
    Args:
        title: String title yang akan di-truncate
        max_length: Maximum karakter yang diizinkan (default: 200)
    
    Returns:
        String: Title yang sudah di-truncate dengan smart logic
    """
    if not title:
        return ""
    
    title = str(title).strip()
    
    # Langkah 1: Kalau <= max_length, aman langsung pakai
    if len(title) <= max_length:
        return title
    
    # Langkah 2: Kalau > max_length, coba smart truncation
    truncated = title[:max_length]
    
    # Cari titik terakhir dalam batas max_length
    last_period_pos = truncated.rfind('.')
    
    # Langkah 2a: Kalau ada titik dalam batas dan tidak di posisi terakhir
    if last_period_pos > 0 and last_period_pos < max_length - 1:
        # Ada titik yang bagus, potong sampai titik terakhir + 1 (include titiknya)
        result = title[:last_period_pos + 1]
        log_message(f"  Smart truncate title: Potong sampai titik terakhir ({len(result)} chars)")
        return result
    
    # Langkah 2b: Tidak ada titik yang cocok, hard truncate + tambah titik
    result = title[:max_length - 1] + '.'
    log_message(f"  Smart truncate title: Hard cut + titik ({len(result)} chars)")
    return result

def sanitize_adobe_stock_title(title):
    """
    Sanitize title untuk Adobe Stock:
    - Smart truncation ke max 200 karakter
    - Tambah titik di akhir
    - Colon (:) boleh tetap
    - Sanitize karakter selain hyphen (-) dan colon (:)
    """
    if not title:
        return ""
    
    # Basic cleanup
    sanitized = re.sub(r'[\r\n\t]+', ' ', str(title))
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Remove special characters except hyphen and colon
    sanitized = re.sub(r'[^\w\s\-:]', '', sanitized)
    
    # Smart truncation SEBELUM tambah titik
    sanitized = smart_truncate_title(sanitized, max_length=200)
    
    # Add period at the end if not already there
    if sanitized and not sanitized.endswith('.'):
        # Cek lagi panjang setelah tambah titik
        if len(sanitized) < 200:
            sanitized += '.'
        else:
            # Kalau udah 200, ganti karakter terakhir dengan titik
            sanitized = sanitized[:-1] + '.'
    
    return sanitized

def sanitize_adobe_stock_keywords(keywords):
    """
    Sanitize keywords untuk Adobe Stock:
    - Hyphen (-) boleh tetap
    - Sanitize karakter selain hyphen
    """
    if isinstance(keywords, list):
        sanitized_list = []
        for keyword in keywords:
            if keyword:
                # Basic cleanup
                clean_kw = re.sub(r'[\r\n\t]+', ' ', str(keyword))
                clean_kw = re.sub(r'\s+', ' ', clean_kw).strip()
                # Remove special characters except hyphen
                clean_kw = re.sub(r'[^\w\s\-]', '', clean_kw)
                if clean_kw:
                    sanitized_list.append(clean_kw)
        return ', '.join(sanitized_list)
    else:
        # String keywords
        clean_kw = re.sub(r'[\r\n\t]+', ' ', str(keywords))
        clean_kw = re.sub(r'\s+', ' ', clean_kw).strip()
        clean_kw = re.sub(r'[^\w\s\-,]', '', clean_kw)
        return clean_kw

def sanitize_vecteezy_title(title):
    """
    Sanitize title untuk Vecteezy:
    - Smart truncation ke max 200 karakter
    - Tambah titik di akhir
    - Colon (:) ganti jadi hyphen (-)
    - Sanitize karakter selain hyphen (-)
    """
    if not title:
        return ""
    
    # Basic cleanup
    sanitized = re.sub(r'[\r\n\t]+', ' ', str(title))
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Replace colon with hyphen
    sanitized = sanitized.replace(':', ' -')
    
    # Remove special characters except hyphen
    sanitized = re.sub(r'[^\w\s\-]', '', sanitized)
    
    # Smart truncation SEBELUM tambah titik
    sanitized = smart_truncate_title(sanitized, max_length=200)
    
    # Add period at the end if not already there
    if sanitized and not sanitized.endswith('.'):
        # Cek lagi panjang setelah tambah titik
        if len(sanitized) < 200:
            sanitized += '.'
        else:
            # Kalau udah 200, ganti karakter terakhir dengan titik
            sanitized = sanitized[:-1] + '.'
    
    return sanitized

def sanitize_vecteezy_keywords(keywords):
    """
    Sanitize keywords untuk Vecteezy:
    - Sanitize SEMUA karakter khusus
    - Hapus kata "vector"
    """
    if isinstance(keywords, list):
        sanitized_list = []
        for keyword in keywords:
            if keyword:
                # Basic cleanup
                clean_kw = re.sub(r'[\r\n\t]+', ' ', str(keyword))
                clean_kw = re.sub(r'\s+', ' ', clean_kw).strip().lower()
                # Remove ALL special characters
                clean_kw = re.sub(r'[^\w\s]', '', clean_kw)
                # Remove "vector" word (including compound words)
                clean_kw = re.sub(r'\bvector\b', '', clean_kw, flags=re.IGNORECASE)
                clean_kw = re.sub(r'vector', '', clean_kw, flags=re.IGNORECASE)  # Remove vector from compound words
                clean_kw = re.sub(r'\s+', ' ', clean_kw).strip()
                if clean_kw:
                    sanitized_list.append(clean_kw)
        return ', '.join(sanitized_list)
    else:
        # String keywords
        clean_kw = re.sub(r'[\r\n\t]+', ' ', str(keywords))
        clean_kw = re.sub(r'\s+', ' ', clean_kw).strip()
        # Remove ALL special characters
        clean_kw = re.sub(r'[^\w\s,]', '', clean_kw)
        # Remove "vector" word (including compound words)
        clean_kw = re.sub(r'\bvector\b', '', clean_kw, flags=re.IGNORECASE)
        clean_kw = re.sub(r'vector', '', clean_kw, flags=re.IGNORECASE)  # Remove vector from compound words
        clean_kw = re.sub(r'\s+', ' ', clean_kw).strip()
        return clean_kw

def write_123rf_csv(csv_path, filename, description, keywords):
    """
    Menulis CSV khusus untuk 123RF dengan format header yang tepat.
    Header: oldfilename,"123rf_filename","description","keywords","country"
    """
    csv_dir = os.path.dirname(csv_path)
    if not os.path.exists(csv_dir):
        try:
            os.makedirs(csv_dir)
        except Exception as e:
            log_message(f"Error: Gagal membuat direktori CSV untuk 123RF: {e}")
            return False
    
    file_exists = os.path.isfile(csv_path)
    try:
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            if not file_exists or os.path.getsize(csv_path) == 0:
                # Header khusus dengan format yang diinginkan
                csvfile.write('oldfilename,"123rf_filename","description","keywords","country"\n')
            
            # Apply smart truncation untuk description sebelum escape quotes
            truncated_description = smart_truncate_description(description, max_length=200)
            
            # Data row - escape quotes dalam data jika ada
            safe_filename = filename.replace('"', '""')
            safe_description = truncated_description.replace('"', '""')
            safe_keywords = keywords.replace('"', '""')
            
            csvfile.write(f'{safe_filename},"","{safe_description}","{safe_keywords}","ID"\n')
        return True
    except Exception as e:
        log_message(f"Error menulis ke CSV 123RF: {e}")
        return False

def write_vecteezy_csv(csv_path, filename, title, description, keywords):
    """
    Menulis CSV khusus untuk Vecteezy dengan filename tanpa quotes.
    Format: filename,title,"description","keywords",pro,
    """
    csv_dir = os.path.dirname(csv_path)
    if not os.path.exists(csv_dir):
        try:
            os.makedirs(csv_dir)
        except Exception as e:
            log_message(f"Error: Gagal membuat direktori CSV untuk Vecteezy: {e}")
            return False
    
    file_exists = os.path.isfile(csv_path)
    try:
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            if not file_exists or os.path.getsize(csv_path) == 0:
                # Header standard
                csvfile.write('Filename,Title,Description,Keywords,License,Id\n')
            
            # Apply smart truncation untuk title dan description sebelum escape quotes
            truncated_title = smart_truncate_title(title, max_length=200)
            truncated_description = smart_truncate_description(description, max_length=200)
            
            # Data row - filename tanpa quotes, lainnya dengan quotes jika perlu
            safe_filename = filename.replace('"', '""')
            safe_title = truncated_title.replace('"', '""')
            safe_description = truncated_description.replace('"', '""')
            safe_keywords = keywords.replace('"', '""')
            
            csvfile.write(f'{safe_filename},{safe_title},"{safe_description}","{safe_keywords}",pro,\n')
        return True
    except Exception as e:
        log_message(f"Error menulis ke CSV Vecteezy: {e}")
        return False

def validate_metadata_completeness(metadata, filename="unknown"):
    """
    Validasi kelengkapan metadata sebelum ditulis ke CSV.
    
    Args:
        metadata: Dictionary metadata dari API atau input
        filename: Nama file untuk logging (optional)
    
    Returns:
        Tuple(bool, dict, list): (is_valid, validated_metadata, issues)
            - is_valid: True jika metadata cukup lengkap untuk CSV
            - validated_metadata: Dictionary metadata yang sudah divalidasi/diperbaiki
            - issues: List of issues yang ditemukan
    """
    issues = []
    validated_metadata = {}
    
    if not metadata:
        issues.append("Metadata kosong atau None")
        return False, {}, issues
    
    if isinstance(metadata, dict):
        # Extract fields from dict result
        title = metadata.get("title", "")
        description = metadata.get("description", "")
        tags = metadata.get("tags", [])
        
        # Validate title
        if not title or not str(title).strip():
            issues.append("Title kosong atau None")
            # Fallback: gunakan filename tanpa ekstensi sebagai title
            base_filename = filename.replace(".jpg", "").replace(".jpeg", "").replace(".png", "").replace(".mp4", "").replace(".eps", "").replace(".ai", "").replace(".svg", "")
            validated_metadata["title"] = base_filename or "Untitled"
            log_message(f"  Warning: Title kosong untuk {filename}, menggunakan filename sebagai fallback", "warning")
        else:
            validated_metadata["title"] = str(title).strip()
        
        # Validate description
        if not description or not str(description).strip():
            issues.append("Description kosong atau None") 
            # Fallback: gunakan title sebagai description
            validated_metadata["description"] = validated_metadata["title"]
            log_message(f"  Warning: Description kosong untuk {filename}, menggunakan title sebagai fallback", "warning")
        else:
            validated_metadata["description"] = str(description).strip()
        
        # Validate tags/keywords
        if not tags or (isinstance(tags, list) and len(tags) == 0):
            issues.append("Tags/keywords kosong atau None")
            # Fallback: buat basic keywords dari title
            title_words = validated_metadata["title"].lower().replace("-", " ").replace("_", " ").split()
            # Filter kata yang terlalu pendek atau umum
            filtered_words = [word for word in title_words if len(word) > 2 and word not in ["the", "and", "for", "with", "from"]]
            validated_metadata["tags"] = filtered_words[:5] if filtered_words else ["image", "stock", "photo"]
            log_message(f"  Warning: Keywords kosong untuk {filename}, generate dari title sebagai fallback", "warning")
        elif isinstance(tags, list):
            # Filter empty/None tags
            cleaned_tags = [str(tag).strip() for tag in tags if tag and str(tag).strip()]
            if not cleaned_tags:
                issues.append("Semua tags kosong setelah cleaning")
                validated_metadata["tags"] = ["image", "stock", "photo"]  # Ultimate fallback
                log_message(f"  Warning: Semua keywords kosong setelah cleaning untuk {filename}", "warning")
            else:
                validated_metadata["tags"] = cleaned_tags
        else:
            # Tags adalah string, convert ke list
            tag_string = str(tags).strip()
            if not tag_string:
                validated_metadata["tags"] = ["image", "stock", "photo"]
                issues.append("Tag string kosong")
            else:
                # Split by comma atau semicolon
                tag_list = [tag.strip() for tag in tag_string.replace(";", ",").split(",") if tag.strip()]
                validated_metadata["tags"] = tag_list if tag_list else ["image", "stock", "photo"]
        
        # Copy kategori dan field lain jika ada
        validated_metadata["as_category"] = metadata.get("as_category", "")
        validated_metadata["ss_category"] = metadata.get("ss_category", "")
        validated_metadata["keyword_count"] = metadata.get("keyword_count", "49")
        
    else:
        # Metadata bukan dict, coba convert
        issues.append(f"Metadata bukan dictionary: {type(metadata)}")
        return False, {}, issues
    
    # Final validation - pastikan semua field essential ada
    essential_fields = ["title", "description", "tags"]
    missing_fields = [field for field in essential_fields if not validated_metadata.get(field)]
    
    if missing_fields:
        issues.append(f"Field essential masih kosong setelah validasi: {missing_fields}")
        return False, validated_metadata, issues
    
    # Success - metadata lengkap
    if issues:
        log_message(f"  Metadata validation: {len(issues)} issue(s) diperbaiki untuk {filename}")
    
    return True, validated_metadata, issues

def write_to_platform_csvs_safe(csv_dir, filename, title, description, keywords, auto_kategori_enabled=True, is_vector=False, max_keywords=49):
    """
    Versi aman dari write_to_platform_csvs dengan validation dan enhanced error handling.
    
    Args:
        csv_dir: Direktori untuk menyimpan file CSV
        filename: Nama file gambar/video yang diproses
        title: Judul metadata atau dict metadata lengkap
        description: Deskripsi metadata
        keywords: List keyword/tag
        auto_kategori_enabled: Flag untuk mengaktifkan penentuan kategori otomatis
        is_vector: Boolean, True jika file asli adalah vektor (eps, ai, svg)
        max_keywords: Maximum number of keywords to include
        
    Returns:
        Tuple(bool, list): (success, failed_platforms)
            - success: True jika minimal 3 dari 5 platform berhasil
            - failed_platforms: List platform yang gagal
    """
    try:
        if not os.path.exists(csv_dir):
            os.makedirs(csv_dir, exist_ok=True)
        
        # Step 1: Validate metadata completeness
        if isinstance(title, dict):
            # title adalah dict metadata lengkap dari API
            is_valid, validated_metadata, issues = validate_metadata_completeness(title, filename)
            if not is_valid:
                log_message(f"  ERROR CSV: Metadata tidak valid untuk {filename}: {issues}", "error")
                return False, ["All platforms - Invalid metadata"]
            
            # Use validated metadata
            safe_title = validated_metadata["title"]
            safe_description = validated_metadata["description"] 
            keywords = validated_metadata["tags"]
        else:
            # title adalah string biasa
            if not title or not str(title).strip():
                log_message(f"  ERROR CSV: Title kosong untuk {filename}", "error")
                # Use filename as fallback
                base_filename = filename.replace(".jpg", "").replace(".jpeg", "").replace(".png", "").replace(".mp4", "").replace(".eps", "").replace(".ai", "").replace(".svg", "")
                safe_title = base_filename or "Untitled"
            else:
                safe_title = str(title).strip()
            
            if not description or not str(description).strip():
                log_message(f"  ERROR CSV: Description kosong untuk {filename}", "error") 
                safe_description = safe_title  # Use title as fallback
            else:
                safe_description = str(description).strip()
                
            if not keywords or (isinstance(keywords, list) and len(keywords) == 0):
                log_message(f"  ERROR CSV: Keywords kosong untuk {filename}", "error")
                keywords = ["image", "stock", "photo"]  # Ultimate fallback
        
        # Step 2: Apply sanitization dan smart truncation
        safe_filename = sanitize_csv_field(filename)
        
        # Apply smart truncation untuk title dan description
        safe_title = smart_truncate_title(sanitize_csv_field(safe_title), max_length=200)
        safe_description = smart_truncate_description(sanitize_csv_field(safe_description), max_length=200)
        
        # Process keywords
        if isinstance(keywords, list):
            # Deduplicate and limit keywords
            keywords = list(dict.fromkeys([k for k in keywords if k and str(k).strip()]))
            keywords = keywords[:max_keywords]
            ss_keywords = ', '.join([sanitize_csv_field(k) for k in keywords if k])
            as_keywords = ', '.join([sanitize_csv_field(k) for k in keywords if k])
        else:
            ss_keywords = sanitize_csv_field(str(keywords))
            as_keywords = sanitize_csv_field(str(keywords))
        
        # Step 3: Validate final data before writing
        if not safe_filename or not safe_title or not safe_description or not (ss_keywords or as_keywords):
            log_message(f"  ERROR CSV: Data final tidak valid setelah sanitasi untuk {filename}", "error")
            return False, ["All platforms - Data validation failed"]
        
        # Step 4: Determine categories
        as_category = ""
        ss_category = ""
        if auto_kategori_enabled:
            as_category = map_to_adobe_stock_category(safe_title, safe_description, keywords if isinstance(keywords, list) else [])
            ss_category = map_to_shutterstock_category(safe_title, safe_description, keywords if isinstance(keywords, list) else [])
            log_message(f"  Auto Kategori: Aktif (AS: {as_category}, SS: {ss_category})")
        else:
            log_message(f"  Auto Kategori: Tidak Aktif")
        
        # Step 5: Write to all platforms with individual error handling
        success_count = 0
        failed_platforms = []
        
        # Adobe Stock
        try:
            as_csv_path = os.path.join(csv_dir, "adobe_stock_export.csv")
            as_header = ["Filename", "Title", "Keywords", "Category", "Releases"]
            as_title_clean = sanitize_adobe_stock_title(safe_title)
            as_keywords_clean = sanitize_adobe_stock_keywords(keywords if isinstance(keywords, list) else as_keywords)
            as_data_row = [safe_filename, as_title_clean, as_keywords_clean, as_category, ""]
            
            if write_to_csv(as_csv_path, as_header, as_data_row):
                success_count += 1
            else:
                failed_platforms.append("Adobe Stock")
        except Exception as e:
            log_message(f"  ERROR CSV Adobe Stock: {e}", "error")
            failed_platforms.append("Adobe Stock")
        
        # ShutterStock  
        try:
            ss_csv_path = os.path.join(csv_dir, "shutterstock_export.csv")
            ss_header = ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"]
            illustration_value = "yes" if is_vector else ""
            ss_data_row = [safe_filename, safe_description, ss_keywords, ss_category, "no", "", illustration_value]
            
            if write_to_csv(ss_csv_path, ss_header, ss_data_row):
                success_count += 1
            else:
                failed_platforms.append("Shutterstock")
        except Exception as e:
            log_message(f"  ERROR CSV Shutterstock: {e}", "error")
            failed_platforms.append("Shutterstock")
        
        # 123RF
        try:
            rf_csv_path = os.path.join(csv_dir, "123rf_export.csv")
            if write_123rf_csv(rf_csv_path, safe_filename, safe_description, as_keywords):
                success_count += 1
            else:
                failed_platforms.append("123RF")
        except Exception as e:
            log_message(f"  ERROR CSV 123RF: {e}", "error")
            failed_platforms.append("123RF")
        
        # Vecteezy
        try:
            vz_csv_path = os.path.join(csv_dir, "vecteezy_export.csv")
            vz_title_clean = sanitize_vecteezy_title(safe_title)
            vz_keywords_clean = sanitize_vecteezy_keywords(keywords if isinstance(keywords, list) else as_keywords)
            if write_vecteezy_csv(vz_csv_path, safe_filename, vz_title_clean, safe_description, vz_keywords_clean):
                success_count += 1
            else:
                failed_platforms.append("Vecteezy")
        except Exception as e:
            log_message(f"  ERROR CSV Vecteezy: {e}", "error")
            failed_platforms.append("Vecteezy")
        
        # Depositphotos
        try:
            dp_csv_path = os.path.join(csv_dir, "depositphotos_export.csv")
            dp_header = ["Filename", "description", "Keywords", "Nudity", "Editorial"]
            dp_data_row = [safe_filename, safe_description, as_keywords, "no", "no"]
            
            if write_to_csv(dp_csv_path, dp_header, dp_data_row):
                success_count += 1
            else:
                failed_platforms.append("Depositphotos")
        except Exception as e:
            log_message(f"  ERROR CSV Depositphotos: {e}", "error")
            failed_platforms.append("Depositphotos")
        
        # Step 6: Create TXT Backups (independent of CSV success/failure)
        backup_dir = os.path.join(csv_dir, "backup")
        try:
            backup_success_count, backup_failed = write_platform_specific_txt_backups(
                backup_dir, safe_filename, safe_title, safe_description, keywords, 
                as_keywords, ss_keywords, as_category, ss_category, is_vector
            )
            
            if backup_success_count >= 3:
                log_message(f"  TXT Backup: {backup_success_count}/5 platform backups berhasil")
            else:
                log_message(f"  TXT Backup: WARNING - Hanya {backup_success_count}/5 backups berhasil", "warning")
                
            if backup_failed:
                log_message(f"  TXT Backup failures: {', '.join(backup_failed)}", "warning")
                
        except Exception as e:
            log_message(f"  TXT Backup: ERROR - {e}", "error")
        
        # Step 7: Evaluate CSV results
        total_platforms = 5
        success_threshold = 3  # Minimal 3 dari 5 platform harus berhasil
        
        if success_count >= success_threshold:
            if failed_platforms:
                log_message(f"  CSV Export: {success_count}/{total_platforms} berhasil. Gagal: {', '.join(failed_platforms)}", "warning")
            else:
                log_message(f"  CSV Export: Berhasil untuk semua {total_platforms} platform")
            return True, failed_platforms
        else:
            log_message(f"  CSV Export: CRITICAL - Hanya {success_count}/{total_platforms} berhasil. Threshold: {success_threshold}", "error")
            return False, failed_platforms
            
    except Exception as e:
        log_message(f"  CRITICAL ERROR CSV: {e}", "error")
        import traceback
        log_message(f"  Traceback: {traceback.format_exc()}", "error")
        return False, ["All platforms - Critical error"]

def write_to_platform_csvs(csv_dir, filename, title, description, keywords, auto_kategori_enabled=True, is_vector=False, max_keywords=49):
    """
    Backward compatible wrapper untuk write_to_platform_csvs_safe.
    Menulis metadata ke file CSV untuk semua platform yang didukung.
    Platform yang didukung: AdobeStock, ShutterStock, 123RF, Vecteezy, Depositphotos
    
    Args:
        csv_dir: Direktori untuk menyimpan file CSV
        filename: Nama file gambar/video yang diproses
        title: Judul metadata atau dict metadata lengkap
        description: Deskripsi metadata
        keywords: List keyword/tag
        auto_kategori_enabled: Flag untuk mengaktifkan penentuan kategori otomatis
        is_vector: Boolean, True jika file asli adalah vektor (eps, ai, svg)
        max_keywords: Maximum number of keywords to include
        
    Returns:
        Boolean: True jika berhasil (minimal 3 dari 5 platform), False jika gagal
    """
    try:
        success, failed_platforms = write_to_platform_csvs_safe(
            csv_dir, filename, title, description, keywords, 
            auto_kategori_enabled, is_vector, max_keywords
        )
        
        # Log additional info for failed platforms if any
        if failed_platforms and success:
            log_message(f"  Note: Beberapa platform gagal tapi masih dalam threshold: {', '.join(failed_platforms)}", "info")
        elif failed_platforms and not success:
            log_message(f"  Critical: Terlalu banyak platform gagal: {', '.join(failed_platforms)}", "error")
        
        return success
        
    except Exception as e:
        log_message(f"  Wrapper Error: {e}", "error")
        return False

def write_txt_backup(backup_dir, platform_name, header, data_rows):
    """
    Menulis backup dalam format TXT dengan format persis sama seperti CSV.
    
    Args:
        backup_dir: Direktori backup
        platform_name: Nama platform (e.g., 'adobe_stock', 'shutterstock')
        header: List header columns
        data_rows: List of data rows (list of lists)
    
    Returns:
        Boolean: True jika berhasil, False jika gagal
    """
    try:
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
        
        backup_file = os.path.join(backup_dir, f"{platform_name}_backup.txt")
        
        with open(backup_file, 'w', newline='', encoding='utf-8') as txtfile:
            # Write header
            if isinstance(header, list):
                # Format header with proper CSV quoting
                header_line = ','.join([f'"{col}"' if ',' in col or '"' in col else col for col in header])
                txtfile.write(header_line + '\n')
            
            # Write data rows
            for row in data_rows:
                if isinstance(row, list):
                    # Format each field with proper CSV escaping
                    formatted_row = []
                    for field in row:
                        field_str = str(field) if field is not None else ""
                        # Escape quotes and wrap in quotes if contains comma or quotes
                        if '"' in field_str:
                            field_str = field_str.replace('"', '""')
                        if ',' in field_str or '"' in field_str or '\n' in field_str:
                            field_str = f'"{field_str}"'
                        formatted_row.append(field_str)
                    txtfile.write(','.join(formatted_row) + '\n')
        
        return True
        
    except Exception as e:
        log_message(f"  Error menulis backup TXT {platform_name}: {e}", "error")
        return False

def write_platform_specific_txt_backups(backup_dir, filename, safe_title, safe_description, keywords, as_keywords, ss_keywords, as_category, ss_category, is_vector=False):
    """
    Menulis backup TXT untuk semua platform dengan format spesifik masing-masing.
    
    Args:
        backup_dir: Direktori backup
        filename: Nama file
        safe_title: Title yang sudah di-sanitize
        safe_description: Description yang sudah di-sanitize  
        keywords: List keywords original
        as_keywords: Adobe Stock formatted keywords
        ss_keywords: Shutterstock formatted keywords
        as_category: Adobe Stock category
        ss_category: Shutterstock category
        is_vector: Boolean vector flag
    
    Returns:
        Tuple(int, list): (success_count, failed_platforms)
    """
    success_count = 0
    failed_platforms = []
    
    # Data untuk setiap platform - format persis sama dengan CSV (RAW data, akan di-format kemudian)
    platform_data = {
        'adobe_stock': {
            'header': ["Filename", "Title", "Keywords", "Category", "Releases"],
            'data': [filename, sanitize_adobe_stock_title(safe_title), sanitize_adobe_stock_keywords(keywords if isinstance(keywords, list) else as_keywords), as_category, ""]
        },
        'shutterstock': {
            'header': ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"],
            'data': [filename, safe_description, ss_keywords, ss_category, "no", "", "yes" if is_vector else ""]
        },
        '123rf': {
            'header': ['oldfilename', '"123rf_filename"', '"description"', '"keywords"', '"country"'],
            'data': [filename, "", safe_description, as_keywords, "ID"]  # RAW data, quotes will be handled by formatting
        },
        'vecteezy': {
            'header': ["Filename", "Title", "Description", "Keywords", "License", "Id"],
            'data': [filename, sanitize_vecteezy_title(safe_title), safe_description, sanitize_vecteezy_keywords(keywords if isinstance(keywords, list) else as_keywords), "pro", ""]  # RAW data
        },
        'depositphotos': {
            'header': ["Filename", "description", "Keywords", "Nudity", "Editorial"],
            'data': [filename, safe_description, as_keywords, "no", "no"]
        }
    }
    
    # Ensure backup directory exists
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)
    
    # Check if backup file already exists, if so read existing data
    existing_data = {}
    for platform_name in platform_data.keys():
        backup_file = os.path.join(backup_dir, f"{platform_name}_backup.txt")
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) > 1:  # Has header + data
                        existing_data[platform_name] = [line.strip() for line in lines[1:]]  # Skip header
                    else:
                        existing_data[platform_name] = []
            except Exception as e:
                log_message(f"  Warning: Gagal baca existing backup {platform_name}: {e}", "warning")
                existing_data[platform_name] = []
        else:
            existing_data[platform_name] = []
    
    # Write backup untuk setiap platform
    for platform_name, data in platform_data.items():
        try:
            # Format new data row properly - handle special cases
            new_row = data['data']
            formatted_new_row = []
            
            for i, field in enumerate(new_row):
                field_str = str(field) if field is not None else ""
                
                # Special handling untuk platform tertentu
                if platform_name == '123rf':
                    # 123RF format: filename,"","description","keywords","ID"
                    if i == 1:  # 123rf_filename column - always empty quoted
                        formatted_new_row.append('""')
                    elif i in [2, 3, 4]:  # description, keywords, country - always quoted
                        escaped_field = field_str.replace('"', '""')
                        formatted_new_row.append(f'"{escaped_field}"')
                    else:  # filename - no quotes
                        formatted_new_row.append(field_str)
                
                elif platform_name == 'vecteezy':
                    # Vecteezy format: filename,title,"description","keywords",pro,
                    if i in [2, 3]:  # description, keywords - quote if contains comma/quotes
                        escaped_field = field_str.replace('"', '""')
                        if ',' in field_str or '"' in field_str or '\n' in field_str:
                            formatted_new_row.append(f'"{escaped_field}"')
                        else:
                            formatted_new_row.append(escaped_field)
                    else:  # other fields - standard handling
                        if ',' in field_str or '"' in field_str or '\n' in field_str:
                            escaped_field = field_str.replace('"', '""')
                            formatted_new_row.append(f'"{escaped_field}"')
                        else:
                            formatted_new_row.append(field_str)
                
                else:
                    # Standard CSV formatting untuk platform lain
                    if '"' in field_str:
                        field_str = field_str.replace('"', '""')
                    if ',' in field_str or '"' in field_str or '\n' in field_str:
                        field_str = f'"{field_str}"'
                    formatted_new_row.append(field_str)
            
            new_row_str = ','.join(formatted_new_row)
            
            # Get existing data (already read as raw lines without header)
            existing_rows = existing_data.get(platform_name, [])
            
            # Filter out empty lines and ensure data integrity
            valid_existing_rows = []
            for row in existing_rows:
                row = row.strip()
                if row and row != '':  # Skip empty lines
                    # Basic validation: ensure row has minimum expected commas
                    expected_commas = len(data['header']) - 1
                    if row.count(',') >= expected_commas:
                        valid_existing_rows.append(row)
                    else:
                        log_message(f"  Warning: Skipping malformed backup row in {platform_name}: {row[:50]}...", "warning")
            
            # Combine valid existing data with new data
            all_data_rows = valid_existing_rows + [new_row_str]
            
            # Write backup file (rewrite completely with header + all data)
            backup_file = os.path.join(backup_dir, f"{platform_name}_backup.txt")
            with open(backup_file, 'w', newline='', encoding='utf-8') as txtfile:
                # Write header
                header = data['header']
                if platform_name == '123rf':
                    # Special header format for 123RF (already formatted)
                    txtfile.write(','.join(header) + '\n')
                else:
                    # Standard header format
                    header_line = ','.join([f'"{col}"' if ',' in col or '"' in col else col for col in header])
                    txtfile.write(header_line + '\n')
                
                # Write all data rows
                for row_str in all_data_rows:
                    if row_str.strip():  # Skip empty lines
                        txtfile.write(row_str + '\n')
            
            success_count += 1
            
        except Exception as e:
            log_message(f"  Error backup TXT {platform_name}: {e}", "error")
            failed_platforms.append(platform_name)
    
    return success_count, failed_platforms
