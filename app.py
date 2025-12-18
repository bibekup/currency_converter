import streamlit as st
import requests
import json
from PyPDF2 import PdfReader
from langdetect import detect_langs
import time
import pyperclip  # Import pyperclip for clipboard operations
import base64
import langcodes  # Import langcodes for language conversion
from gtts import gTTS 
import os



# LLM-Endpoint URL
LLM_ENDPOINT = "https://chat-large.llm.mylab.th-luebeck.dev/v1"
# Multilingual e5 large Text Embedding Endpoint
EMBEDDING_ENDPOINT = "https://bge-m3.models.th-luebeck.dev"

# Function to call the LLM endpoint for text summarization
def summarize_text(text, language, max_tokens=150):
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "tgi",
        "messages": [
            {"role": "system", "content": f"You are a helpful assistant. Please summarize the text in {language}."},
            {"role": "user", "content": f"Summarize the following text and ensure the summary is in {language}: {text}"}
        ],
        "max_tokens": max_tokens,
        "stream": False
    }
    
    try:
        response = requests.post(f"{LLM_ENDPOINT}/chat/completions", headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and result["choices"]:
            return result['choices'][0]['message']['content']
        else:
            return "No valid response received."
    
    except requests.exceptions.HTTPError as e:
        return f"Error requesting LLM endpoint: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error requesting LLM endpoint: {e}"
    except json.JSONDecodeError:
        return "Error parsing server response as JSON."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# Function to extract text from a PDF file
def extract_text_from_pdf(file, max_pages=None):
    try:
        pdf_reader = PdfReader(file)
        text = ""
        num_pages = len(pdf_reader.pages)
        max_pages = max_pages or num_pages  # Process all pages if max_pages is not set
        
        for page_num in range(min(max_pages, num_pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        
        return text
    except Exception as e:
        return f"Error extracting text from PDF file: {e}"

def summarize_large_text(text, language, chunk_size=2000, max_tokens=150, show_progress=True):
    summaries = []
    text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    for i, chunk in enumerate(text_chunks):
        if show_progress:
            st.text(f"Processing section {i+1} of {len(text_chunks)}...")
        
        summary = summarize_text(chunk, language, max_tokens)
        
        if summary.startswith("Error"):
            st.error(summary)
            break
        else:
            # Clean up the summary by removing unwanted phrases
            cleaned_summary = summary.replace("Here is a summary of the text in English:", "").strip()
            
            if language != "en":  # Check if the detected language is not English
                summary_language, _ = detect_language(cleaned_summary)
                if summary_language != language:
                    translated_summary = translate_text(cleaned_summary, language)
                    if translated_summary.startswith("Error"):
                        st.warning(f"Translation failed: {translated_summary}")
                        summaries.append(cleaned_summary)  # Append original summary if translation fails
                    else:
                        summaries.append(translated_summary)
                else:
                    summaries.append(cleaned_summary)
            else:
                summaries.append(cleaned_summary)
        
        time.sleep(1)  # Avoid exceeding API rate limits
    
    # Join all summaries into a single output
    full_summary = "\n\n".join(summaries)
    return full_summary

# Function to detect language
def detect_language(text):
    try:
        languages = detect_langs(text)
        primary_language = languages[0].lang
        confidence = languages[0].prob
        return primary_language, confidence
    except Exception as e:
        return "unknown", 0.0

# Function to translate text using Multilingual e5 large model
def translate_text(text, dest_language):
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "text": text,
            "target_lang": dest_language
        }
        response = requests.post(f"{EMBEDDING_ENDPOINT}/translate", headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        return result['translation']
    except requests.exceptions.HTTPError as e:
        return f"Error translating text: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error translating text: {e}"
    except json.JSONDecodeError:
        return "Error parsing server response as JSON."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# Function to create a download link for the summary
def download_link(object_to_download, download_filename, download_link_text):
    try:
        # some strings <-> bytes conversions necessary here
        b64 = base64.b64encode(object_to_download.encode()).decode()
        return f'<a href="data:file/txt;base64,{b64}" download="{download_filename}">{download_link_text}</a>'
    except Exception as e:
        return f"Error creating download link: {e}"

# Function to validate and convert language input to language code
def validate_language(language_input):
    try:
        language = langcodes.find(language_input).language
        return language
    except Exception as e:
        return f"Error validating language: {e}"
    

# Main function to run the Streamlit app
def main():
    st.title("PDF Text Summarization")
    
    # Clear summary button
    if st.button("Clear Summary"):
        st.session_state.summary_text = ""
        st.session_state.last_file = None
        st.success("Summary cleared. You can upload a new PDF.")
        st.rerun()  # Refresh the app state after clearing
    
    uploaded_file = st.file_uploader("Upload your PDF file", type=['pdf'])
    max_tokens = st.slider("Maximum Tokens for Summary", min_value=50, max_value=500, value=150)
    chunk_size = st.slider("Chunk Size for Summarization", min_value=500, max_value=5000, value=2000)
    language_input = st.text_input("Enter the desired language for the summary (e.g., 'English', 'French', 'German')", "English")
    
    # Validate the language input and convert to language code
    language_code = validate_language(language_input)
    if language_code.startswith("Error"):
        st.error(language_code)
        return
    
    # Initialize session state to store summarized text
    if 'summary_text' not in st.session_state:
        st.session_state.summary_text = ""
    if 'last_file' not in st.session_state:
        st.session_state.last_file = None

    if uploaded_file is not None:
        st.info("PDF file uploaded successfully.")
        
        # Reset the summary for a new file
        if st.session_state.last_file != uploaded_file:
            st.session_state.summary_text = ""
            st.session_state.last_file = uploaded_file
        
        # Create summary if not already created
        if not st.session_state.summary_text:
            text = extract_text_from_pdf(uploaded_file)
            if text.startswith("Error"):
                st.error(text)
            elif text.strip() == "":
                st.error("The PDF file contains no extractable text.")
            else:
                st.success("Text extracted from PDF file.")
                
                # Detect language
                detected_language, confidence = detect_language(text)
                st.info(f"Detected language: {detected_language} with confidence: {confidence}")
                
                summary_text = summarize_large_text(text, language_code, chunk_size=chunk_size, max_tokens=max_tokens)
                if summary_text.startswith("Error"):
                    st.error(summary_text)
                else:
                    st.success("Summary created.")
                    st.session_state.summary_text = summary_text  # Store summarized text in session state
        
        # Display summary in a text area
        if st.session_state.summary_text:
            summary_text_area = st.text_area("PDF Summary", st.session_state.summary_text, height=300)
            # Copy summary to clipboard on button click
            if st.button("Copy Summary"):
                pyperclip.copy(st.session_state.summary_text)
                st.success("Summary copied to clipboard! You can now paste it elsewhere.")
            
            # Download summary button
            if st.button("Download Summary"):
                tmp_download_link = download_link(st.session_state.summary_text, 'summary.txt', 'Click here to download your summary!')
                st.markdown(tmp_download_link, unsafe_allow_html=True)
            

if __name__== "__main__":
    main()