"""
Chandra OCR API Client

This module provides functions to interact with the Chandra OCR API server.
The API server must be running at http://101.53.140.236:8080 before using these functions.
"""

import requests
import base64
from typing import Optional, Dict, Any, Union
from pathlib import Path


def check_api_health(base_url: str = "http://101.53.140.236:8080") -> bool:
    """
    Check if the Chandra OCR API server is running and healthy.
    
    Args:
        base_url: Base URL of the API server (default: http://101.53.140.236:8080)
    
    Returns:
        bool: True if API is healthy, False otherwise
    """
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def process_document(
    file_path: Union[str, Path],
    base_url: str = "http://101.53.140.236:8080",
    page_number: Optional[int] = None,
    max_output_tokens: int = 7000,
    include_images: bool = True,
    include_headers_footers: bool = False,
    method: str = "vllm"
) -> Dict[str, Any]:
    """
    Process a document (image or PDF) using the Chandra OCR API.
    
    Args:
        file_path: Path to the image or PDF file to process
        base_url: Base URL of the API server (default: http://101.53.140.236:8080)
        page_number: For PDFs, which page to process (0-indexed). If None, all pages are processed.
        max_output_tokens: Maximum tokens for output (default: 7000)
        include_images: Whether to extract images from document (default: True)
        include_headers_footers: Whether to include headers/footers (default: False)
        method: Processing method - "vllm" or "hf" (default: "vllm")
    
    Returns:
        dict: API response containing:
            - success: bool
            - num_pages: int
            - markdown: str
            - html: str
            - token_count: int
            - pages: list of page objects
    
    Raises:
        FileNotFoundError: If the file_path does not exist
        requests.exceptions.RequestException: If the API request fails
        ValueError: If the API returns an error response
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Prepare the request data
    url = f"{base_url}/ocr"
    files = {'file': open(file_path, 'rb')}
    data = {
        'max_output_tokens': max_output_tokens,
        'include_images': include_images,
        'include_headers_footers': include_headers_footers,
        'method': method
    }
    
    # Add page_number if specified
    if page_number is not None:
        data['page_number'] = page_number
    
    try:
        # Make the API request
        response = requests.post(url, files=files, data=data, timeout=300)
        files['file'].close()
        
        # Check if request was successful
        response.raise_for_status()
        
        # Parse JSON response
        result = response.json()
        
        # Check if API returned an error
        if not result.get('success', False):
            error_msg = result.get('error', 'Unknown error occurred')
            raise ValueError(f"API returned error: {error_msg}")
        
        return result
        
    except requests.exceptions.Timeout:
        raise requests.exceptions.RequestException("Request timed out. The document may be too large or the server is busy.")
    except requests.exceptions.HTTPError as e:
        raise requests.exceptions.RequestException(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Request failed: {e}")
    finally:
        # Ensure file is closed even if an error occurs
        if 'files' in locals() and not files['file'].closed:
            files['file'].close()


def process_base64_image(
    image_base64: str,
    base_url: str = "http://101.53.140.236:8080",
    max_output_tokens: int = 7000,
    method: str = "vllm"
) -> Dict[str, Any]:
    """
    Process a base64-encoded image using the Chandra OCR API.
    
    Args:
        image_base64: Base64-encoded image string
        base_url: Base URL of the API server (default: http://101.53.140.236:8080)
        max_output_tokens: Maximum tokens for output (default: 7000)
        method: Processing method - "vllm" or "hf" (default: "vllm")
    
    Returns:
        dict: API response containing:
            - success: bool
            - num_pages: int
            - markdown: str
            - html: str
            - token_count: int
            - pages: list of page objects
    
    Raises:
        requests.exceptions.RequestException: If the API request fails
        ValueError: If the API returns an error response
    """
    url = f"{base_url}/ocr/base64"
    data = {
        'image_base64': image_base64,
        'max_output_tokens': max_output_tokens,
        'method': method
    }
    
    try:
        # Make the API request
        response = requests.post(url, data=data, timeout=300)
        
        # Check if request was successful
        response.raise_for_status()
        
        # Parse JSON response
        result = response.json()
        
        # Check if API returned an error
        if not result.get('success', False):
            error_msg = result.get('error', 'Unknown error occurred')
            raise ValueError(f"API returned error: {error_msg}")
        
        return result
        
    except requests.exceptions.Timeout:
        raise requests.exceptions.RequestException("Request timed out. The image may be too large or the server is busy.")
    except requests.exceptions.HTTPError as e:
        raise requests.exceptions.RequestException(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Request failed: {e}")


def process_image_file_as_base64(
    image_path: Union[str, Path],
    base_url: str = "http://101.53.140.236:8080",
    max_output_tokens: int = 7000,
    method: str = "vllm"
) -> Dict[str, Any]:
    """
    Helper function to process an image file by converting it to base64 first.
    
    Args:
        image_path: Path to the image file
        base_url: Base URL of the API server (default: http://101.53.140.236:8080)
        max_output_tokens: Maximum tokens for output (default: 7000)
        method: Processing method - "vllm" or "hf" (default: "vllm")
    
    Returns:
        dict: API response (same as process_base64_image)
    
    Raises:
        FileNotFoundError: If the image_path does not exist
        requests.exceptions.RequestException: If the API request fails
    """
    image_path = Path(image_path)
    
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Read image file and encode to base64
    with open(image_path, 'rb') as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    
    return process_base64_image(image_base64, base_url, max_output_tokens, method)


# Example usage
if __name__ == "__main__":
    """
    When you run this file directly:
    - It will call the Chandra OCR API with `sample-1.pdf`
    - It will save the markdown OCR output to `Ocr_output.md`
    """

    input_path = Path("cortex-sample-5.pdf")  # Change this if your file is elsewhere
    output_path = Path("Ocr_output.md")

    print("Checking API health...")
    if not check_api_health():
        print("✗ API is not available. Make sure the server is running at http://101.53.140.236:8080")
        exit(1)

    if not input_path.exists():
        print(f"✗ Input file not found: {input_path.resolve()}")
        print("   Put your `sample-1.pdf` in the project folder or update `input_path` in chandra_ocr_client.py.")
        exit(1)

    try:
        result = process_document(
            file_path=input_path,
            max_output_tokens=7000,
            method="vllm",
        )

        # Save only the markdown content to a separate text file
        markdown_text = result.get("markdown", "")
        output_path.write_text(markdown_text, encoding="utf-8")

        print(f"\n✓ Processed {result['num_pages']} page(s)")
        print(f"Token count: {result['token_count']}")
        print(f"Markdown saved to: {output_path.resolve()}")
    except Exception as e:
        print(f"Error during OCR: {e}")

