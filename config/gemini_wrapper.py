from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
from utils import info, error, warning, critical
from constant import AI
from datetime import datetime,timedelta
from time import sleep
import math
import random

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY is None:
    critical("Environment variable 'GEMINI_API_KEY' is not set")
    exit(1)

generative_ai = genai.Client(api_key=GEMINI_API_KEY)

DEFAULT_GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.7,
    top_p=0.95,
    top_k=40,
    max_output_tokens=8192,
    response_mime_type='text/plain',
    safety_settings=[
        types.SafetySetting(
            category='HARM_CATEGORY_HATE_SPEECH',
            threshold='BLOCK_MEDIUM_AND_ABOVE'
        ),
        types.SafetySetting(
            category='HARM_CATEGORY_HARASSMENT',
            threshold='BLOCK_MEDIUM_AND_ABOVE'
        ),
        types.SafetySetting(
            category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
            threshold='BLOCK_MEDIUM_AND_ABOVE'
        ),
        types.SafetySetting(
            category='HARM_CATEGORY_DANGEROUS_CONTENT',
            threshold='BLOCK_MEDIUM_AND_ABOVE'
        ),
    ]
)


class RateLimit:
    def __init__(self, session, max_request):
        self.session = session
        self.max_request = max_request
        self.request = []

    def __clean_old_request(self):
        now = datetime.now()
        cut_off = now - timedelta(milliseconds=self.session)
        self.request = [req_time for req_time in self.request if req_time > cut_off]

    def waitIfNeeded(self):
        try:
            self.__clean_old_request()
            if len(self.request) < self.max_request:
                self.request.append(datetime.now())
                return 0

            oldest_request = self.request[0]
            time_interval = (datetime.now() - oldest_request).total_seconds()

            sleep(time_interval)
            self.request.append(datetime.now())
            return time_interval
        except Exception as e:
            error(f"Error in waitIfNeeded: {e}")
            return -1

    def getStats(self):
        self.__clean_old_request()
        return {
            "current_requests": len(self.request),
            "max_requests": self.max_request,
            "window_ms": self.session
        }


ratelimit = RateLimit(session=60 * 1000, max_request=AI.MAX_REQUESTS_PER_MINUTE)

def estimated_input_tokens(prompt: str):
    if not prompt:
        warning("Empty text provided for token estimation")
        return 0
    length = len(prompt)
    token = length / 4
    with_buffer = token * 1.1
    return math.ceil(with_buffer)

def validate(prompt: str):
    estimated_tokens = estimated_input_tokens(prompt)
    if estimated_tokens > AI.MAX_INPUT_TOKENS:
        return {
            'valid': False,
            'estimatedTokens': estimated_tokens,
            'maxTokens': AI.MAX_INPUT_TOKENS,
            'message': f'Input too large: {estimated_tokens} tokens (max: {AI.MAX_INPUT_TOKENS})'
        }
    return {
        'valid': True,
        'estimatedTokens': estimated_tokens,
        'maxTokens': AI.MAX_INPUT_TOKENS,
        'message': 'Input size valid'
    }


def backoff_request(fn, max_retries=AI.MAX_RETRIES):
    attempt = 0
    last_error = None

    while attempt < max_retries:
        try:
            result = fn()

            return result
        except Exception as e:
            last_error = e
            attempt += 1

            if attempt >= max_retries:
                error(f"Max retries reached: {e}")
                raise last_error

            base_delay = AI.RETRY_DELAY
            exponential_delay = base_delay * pow(AI.BACKOFF_MULTIPLIER, attempt)
            jitter = 0.8 + (random.random() * 0.4)
            final_delay = math.floor(exponential_delay * jitter) / 1000

            error(f"Attempt {attempt} failed: {last_error}")
            info(f"Retrying in {final_delay}s...")

            sleep(final_delay)

    raise last_error


def generate_content_call(prompt):
    response = generative_ai.models.generate_content(
        model=AI.MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=AI.TEMPERATURE,
            top_p=AI.TOP_P,
            top_k=AI.TOP_K,
            max_output_tokens=AI.MAX_OUTPUT_TOKENS,
            safety_settings=[
                types.SafetySetting(
                    category='HARM_CATEGORY_DANGEROUS_CONTENT',
                    threshold='BLOCK_MEDIUM_AND_ABOVE'
                ),
                types.SafetySetting(
                    category='HARM_CATEGORY_HARASSMENT',
                    threshold='BLOCK_MEDIUM_AND_ABOVE'
                ),
                types.SafetySetting(
                    category='HARM_CATEGORY_HATE_SPEECH',
                    threshold='BLOCK_MEDIUM_AND_ABOVE'
                ),
                types.SafetySetting(
                    category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                    threshold='BLOCK_ONLY_HIGH'
                ),
            ]
        )
    )
    return response


def generate_content(prompt):
    try:
        validation = validate(prompt)
        if not validation["valid"]:
            error(validation["message"])
            return {
                "success": False,
                "response": None,
                "error": validation["message"],
                "metadata": {
                    "estimatedInputTokens": validation["estimatedTokens"],
                    "rateLimitStats": ratelimit.getStats()
                }
            }
        else:
            info("Prompt is valid")
        wait_result = ratelimit.waitIfNeeded()
        if wait_result == -1:
            return {
                "success": False,
                "response": None,
                "error": "Rate limit error",
                "metadata": {
                    "estimatedInputTokens": validation["estimatedTokens"],
                    "rateLimitStats": ratelimit.getStats()
                }
            }
        result = backoff_request(lambda: generate_content_call(prompt))
        text = result.text

        return {
            "success": True,
            "response": text,
            "error": None,
            "metadata": {
                "estimatedInputTokens": validation["estimatedTokens"],
                "rateLimitStats": ratelimit.getStats()
            }
        }

    except Exception as e:
        error(f"Error generating content: {e}")
        return {
            "success": False,
            "response": None,
            "error": str(e),
            "metadata": {
                "estimatedInputTokens": 0,
                "rateLimitStats": ratelimit.getStats()
            }
        }

def test_connection():
    try:
        res = generate_content(prompt="Say 'Ok' if you can see this message.")
        if res['success']:
            info(f"Connection successful.\n{res["response"]}")
            return {
                "success": True,
                "data": "Connection successful",
                "error": None
            }
        else:
            return {
                "success": False,
                "data": None,
                "error": res["error"]
            }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e)
        }



if __name__ == "__main__":
    result = test_connection()
    if not result['success']:
        exit(1)