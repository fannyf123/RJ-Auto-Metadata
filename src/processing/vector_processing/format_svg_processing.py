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

# src/processing/vector_processing/format_svg_processing.py
import os
import platform
from src.utils.logging import log_message
from src.api.gemini_api import check_stop_event

def convert_svg_to_jpg(svg_path, output_jpg_path, stop_event=None):
    filename = os.path.basename(svg_path)
    log_message(f"Trying to convert SVG to JPG: {filename}")
    
    if check_stop_event(stop_event, f"Conversion of SVG cancelled: {filename}"):
        return False, f"Conversion cancelled: {filename}"
    if platform.system() in ["Darwin", "Linux"]:
        success, error = _convert_svg_with_cairosvg(svg_path, output_jpg_path, stop_event)
        if success:
            return True, None
        else:
            log_message(f"CairoSVG conversion failed: {error}", "warning")
    success, error = _convert_svg_with_svglib(svg_path, output_jpg_path, stop_event)
    if success:
        return True, None
    else:
        log_message(f"svglib conversion failed: {error}", "warning")
    success, error = _convert_svg_with_ghostscript(svg_path, output_jpg_path, stop_event)
    if success:
        return True, None
    else:
        log_message(f"Ghostscript conversion failed: {error}", "warning")
    
    return False, f"All SVG conversion methods failed for: {filename}"

def _convert_svg_with_cairosvg(svg_path, output_jpg_path, stop_event=None):
    try:
        import cairosvg
        from PIL import Image
        import io
        
        filename = os.path.basename(svg_path)
        
        if check_stop_event(stop_event):
            return False, "Conversion cancelled"
        png_data = cairosvg.svg2png(url=svg_path)
        
        if check_stop_event(stop_event):
            return False, "Conversion cancelled"
        img = Image.open(io.BytesIO(png_data))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        img.save(output_jpg_path, 'JPEG', quality=95, optimize=True)
        
        if os.path.exists(output_jpg_path) and os.path.getsize(output_jpg_path) > 0:
            try:
                from src.utils.compression import compress_image
                compressed_path, is_compressed = compress_image(output_jpg_path, os.path.dirname(output_jpg_path))
                if is_compressed and compressed_path and os.path.exists(compressed_path):
                    try:
                        os.replace(compressed_path, output_jpg_path)
                    except Exception:
                        pass
            except Exception as e_comp:
                log_message(f"Warning: Failed to compress rasterized SVG: {e_comp}")
            return True, None
        else:
            return False, "Output file is empty or not created"
            
    except ImportError:
        return False, "CairoSVG not available"
    except Exception as e:
        return False, f"CairoSVG error: {e}"

def _convert_svg_with_svglib(svg_path, output_jpg_path, stop_event=None):
    """Convert SVG using svglib + reportlab (original method)"""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        
        filename = os.path.basename(svg_path)
        
        if check_stop_event(stop_event):
            return False, "Conversion cancelled"
        
        drawing = svg2rlg(svg_path)
        if drawing is None:
            return False, "Failed to parse SVG"
        
        if check_stop_event(stop_event):
            return False, "Conversion cancelled after parse"
        
        renderPM.drawToFile(drawing, output_jpg_path, fmt="JPEG", bg=0xFFFFFF)
        
        if os.path.exists(output_jpg_path) and os.path.getsize(output_jpg_path) > 0:
            try:
                from src.utils.compression import compress_image
                compressed_path, is_compressed = compress_image(output_jpg_path, os.path.dirname(output_jpg_path))
                if is_compressed and compressed_path and os.path.exists(compressed_path):
                    try:
                        os.replace(compressed_path, output_jpg_path)
                    except Exception:
                        pass
            except Exception as e_comp:
                log_message(f"Warning: Failed to compress rasterized SVG: {e_comp}")
            return True, None
        else:
            return False, "Output file is empty or not created"
            
    except ImportError:
        return False, "svglib or reportlab not available"
    except Exception as e:
        return False, f"svglib error: {e}"

def _convert_svg_with_ghostscript(svg_path, output_jpg_path, stop_event=None):
    """Convert SVG using Ghostscript as fallback"""
    try:
        import subprocess
        from src.utils.system_checks import GHOSTSCRIPT_PATH
        
        if not GHOSTSCRIPT_PATH:
            return False, "Ghostscript not available"
        
        filename = os.path.basename(svg_path)
        
        if check_stop_event(stop_event):
            return False, "Conversion cancelled"
        cmd = [
            GHOSTSCRIPT_PATH,
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=jpeg",
            "-dJPEGQ=95",
            "-r300", 
            "-dGraphicsAlphaBits=4",
            "-dTextAlphaBits=4",
            f"-sOutputFile={output_jpg_path}",
            svg_path
        ]
        
        creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=creation_flags
        )
        
        if check_stop_event(stop_event):
            return False, "Conversion cancelled"
        
        if result.returncode == 0 and os.path.exists(output_jpg_path) and os.path.getsize(output_jpg_path) > 0:
            try:
                from src.utils.compression import compress_image
                compressed_path, is_compressed = compress_image(output_jpg_path, os.path.dirname(output_jpg_path))
                if is_compressed and compressed_path and os.path.exists(compressed_path):
                    try:
                        os.replace(compressed_path, output_jpg_path)
                    except Exception:
                        pass
            except Exception as e_comp:
                log_message(f"Warning: Failed to compress rasterized SVG: {e_comp}")
            return True, None
        else:
            return False, f"Ghostscript failed (code {result.returncode}): {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "Ghostscript conversion timeout"
    except Exception as e:
        return False, f"Ghostscript error: {e}"