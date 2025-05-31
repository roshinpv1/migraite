import os
import logging
import json
from datetime import datetime
import requests

# Configure logging
log_directory = os.getenv("LOG_DIR", "logs")
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(
    log_directory, f"llm_calls_{datetime.now().strftime('%Y%m%d')}.log"
)

# Set up logger
logger = logging.getLogger("llm_logger")
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent propagation to root logger
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

# Simple cache configuration
cache_file = "llm_cache.json"


# # By default, we Google Gemini 2.5 pro, as it shows great performance for code understanding
# def call_llm(prompt: str, use_cache: bool = True) -> str:
#     # Log the prompt
#     logger.info(f"PROMPT: {prompt}")

#     # Check cache if enabled
#     if use_cache:
#         # Load cache from disk
#         cache = {}
#         if os.path.exists(cache_file):
#             try:
#                 with open(cache_file, "r") as f:
#                     cache = json.load(f)
#             except:
#                 logger.warning(f"Failed to load cache, starting with empty cache")

#         # Return from cache if exists
#         if prompt in cache:
#             logger.info(f"RESPONSE: {cache[prompt]}")
#             return cache[prompt]

#     # # Call the LLM if not in cache or cache disabled
#     # client = genai.Client(
#     #     vertexai=True,
#     #     # TODO: change to your own project id and location
#     #     project=os.getenv("GEMINI_PROJECT_ID", "your-project-id"),
#     #     location=os.getenv("GEMINI_LOCATION", "us-central1")
#     # )

#     # You can comment the previous line and use the AI Studio key instead:
#     client = genai.Client(
#         api_key=os.getenv("GEMINI_API_KEY", ""),
#     )
#     model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-exp-03-25")
#     # model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-04-17")
    
#     response = client.models.generate_content(model=model, contents=[prompt])
#     response_text = response.text

#     # Log the response
#     logger.info(f"RESPONSE: {response_text}")

#     # Update cache if enabled
#     if use_cache:
#         # Load cache again to avoid overwrites
#         cache = {}
#         if os.path.exists(cache_file):
#             try:
#                 with open(cache_file, "r") as f:
#                     cache = json.load(f)
#             except:
#                 pass

#         # Add to cache and save
#         cache[prompt] = response_text
#         try:
#             with open(cache_file, "w") as f:
#                 json.dump(cache, f)
#         except Exception as e:
#             logger.error(f"Failed to save cache: {e}")

#     return response_text


# # Use Anthropic Claude 3.7 Sonnet Extended Thinking
# def call_llm(prompt, use_cache: bool = True):
#     from anthropic import Anthropic
#     client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "your-api-key"))
#     response = client.messages.create(
#         model="claude-3-7-sonnet-20250219",
#         max_tokens=21000,
#         thinking={
#             "type": "enabled",
#             "budget_tokens": 20000
#         },
#         messages=[
#             {"role": "user", "content": prompt}
#         ]
#     )
#     return response.content[1].text

# Use OpenAI o1
def call_llm(prompt, use_cache: bool = True):
    try:
        from openai import OpenAI
        
        # Log that we're starting the LLM call
        logger.info(f"Starting LLM call, use_cache={use_cache}")
        
        # Calculate approximate token count (rough estimate)
        def estimate_tokens(text):
            # Average English text has ~4 characters per token
            return len(text) // 4
        
        # Check if the prompt is too large (8k tokens is a safe limit for most models)
        max_tokens = 8000
        estimated_tokens = estimate_tokens(prompt)
        
        if estimated_tokens > max_tokens:
            logger.warning(f"Prompt too large: ~{estimated_tokens} tokens. Truncating to ~{max_tokens} tokens.")
            # Keep first and last parts of the prompt
            chars_to_keep = max_tokens * 4
            first_part = prompt[:chars_to_keep // 2]
            last_part = prompt[-(chars_to_keep // 2):]
            prompt = first_part + "\n\n[...content truncated due to length...]\n\n" + last_part
        
        # Log that we're creating the OpenAI client
        logger.info("Creating OpenAI client")
        
        # Explicitly set only the required parameters for OpenAI client
        # This prevents any system-level proxy settings from being passed
        client_kwargs = {
            "api_key": os.environ.get("OPENAI_API_KEY", "your-api-key"),
            "base_url": os.environ.get("OPENAI_URL", "http://localhost:1234/v1")
        }
        
        # Create client with only the supported parameters
        client = OpenAI(**client_kwargs)
        
        # Log that we're making the API call
        logger.info("Making API call to OpenAI")
        
        r = client.chat.completions.create(
            model="o1",
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort="medium",
            store=False
        )
        
        # Log successful completion
        logger.info("Successfully received response from OpenAI")
        
        return r.choices[0].message.content
        
    except Exception as e:
        print(  f"Error in call_llm: {str(e)}")
        # Log the exception details
        error_message = f"Error in call_llm: {str(e)}"
        logger.error(error_message)
        logger.error(f"Exception type: {type(e).__name__}")
        
        # Log additional context that might help diagnose the issue
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        if "proxies" in str(e):
            logger.error("This appears to be a proxy configuration error. Make sure your system proxy settings are correctly configured.")
        
        # Return a fallback response or re-raise the exception
        fallback_response = "I'm sorry, but I encountered an error while processing your request. Please try again later."
        logger.info(f"Returning fallback response: {fallback_response}")
        return fallback_response

# Use OpenRouter API
# def call_llm(prompt: str, use_cache: bool = True) -> str:
#     # Log the prompt
#     logger.info(f"PROMPT: {prompt}")

#     # Check cache if enabled
#     if use_cache:
#         # Load cache from disk
#         cache = {}
#         if os.path.exists(cache_file):
#             try:
#                 with open(cache_file, "r") as f:
#                     cache = json.load(f)
#             except:
#                 logger.warning(f"Failed to load cache, starting with empty cache")

#         # Return from cache if exists
#         if prompt in cache:
#             logger.info(f"RESPONSE: {cache[prompt]}")
#             return cache[prompt]

#     # OpenRouter API configuration
#     api_key = os.getenv("OPENROUTER_API_KEY", "")
#     model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
    
#     headers = {
#         "Authorization": f"Bearer {api_key}",
#     }

#     data = {
#         "model": model,
#         "messages": [{"role": "user", "content": prompt}]
#     }

#     response = requests.post(
#         "https://openrouter.ai/api/v1/chat/completions",
#         headers=headers,
#         json=data
#     )

#     if response.status_code != 200:
#         error_msg = f"OpenRouter API call failed with status {response.status_code}: {response.text}"
#         logger.error(error_msg)
#         raise Exception(error_msg)
#     try:
#         response_text = response.json()["choices"][0]["message"]["content"]
#     except Exception as e:
#         error_msg = f"Failed to parse OpenRouter response: {e}; Response: {response.text}"
#         logger.error(error_msg)        
#         raise Exception(error_msg)
    

#     # Log the response
#     logger.info(f"RESPONSE: {response_text}")

#     # Update cache if enabled
#     if use_cache:
#         # Load cache again to avoid overwrites
#         cache = {}
#         if os.path.exists(cache_file):
#             try:
#                 with open(cache_file, "r") as f:
#                     cache = json.load(f)
#             except:

#                 pass

#         # Add to cache and save
#         cache[prompt] = response_text
#         try:
#             with open(cache_file, "w") as f:
#                 json.dump(cache, f)
#         except Exception as e:
#             logger.error(f"Failed to save cache: {e}")

#     return response_text

if __name__ == "__main__":
    test_prompt = "Hello, how are you?"

    # First call - should hit the API
    print("Making call...")
    response1 = call_llm(test_prompt, use_cache=False)
    print(f"Response: {response1}")
