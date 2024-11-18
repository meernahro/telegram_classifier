from openai import OpenAI
import logging
import json

class OpenAIClient:
    def __init__(self, api_key: str):
        self.client = OpenAI()
    
    def classify_message(self, message: str) -> list:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "you are a classifier function. You will receive a message that might contain which token or tokens is listed or going to be listed or launched on spot or future perpetuals on which exchange on spot or future. the message might not even talk about token listing so don't give false positives. or job is to identify name of the token or tokens (without usdt). return only JSON in ARRAY , NO TALKING. if the message doesn't talk about a token being listed, return []. if 1 token, return for example [{\"token\": \"ABCD\",\"exchange\": \"binance\",\"market\": \"future\"}] . if two or more tokens, put them in the array."
                    },
                    {"role": "user", "content": message}
                ],
                temperature=1,
                max_tokens=2048,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={"type": "text"}
            )
            
            result = response.choices[0].message.content
            
            logging.info(f"OpenAI raw response: {result}")
            
            try:
                parsed_result = json.loads(result)
                if isinstance(parsed_result, list):
                    return parsed_result
                logging.error(f"Response is not a list: {result}")
                return []
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse OpenAI response as JSON: {result}")
                logging.error(f"JSON parse error: {str(e)}")
                return []
                
        except Exception as e:
            logging.error(f"Error in OpenAI request: {str(e)}")
            return []
