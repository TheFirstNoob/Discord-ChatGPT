import re
from typing import List, Tuple, Optional, Union
from discord import Embed, Message, Interaction
from src.locale_manager import locale_manager as lm

# Constants
CHAR_LIMIT = 1900  # Limit for regular messages
EMBED_CHAR_LIMIT = 4096  # Limit for Embed field
CODE_BLOCK_PATTERN = r'```([a-zA-Z]*)\n(.*?)```'
THINKING_PATTERN = re.compile(r'<think>(.*?)</think>', re.DOTALL)
REASONING_PATTERN = re.compile(r'Started reasoning...(.*?)Done in \d+s\.', re.DOTALL)

async def send_split_message(self, response: str, message: Union[Message, Interaction]) -> None:
   """
   Split and send a message that might exceed Discord's character limits.
   
   Args:
       response: The message content to send
       message: Discord message or interaction object
   """
   if hasattr(message, 'followup'):
       send_method = message.followup.send
   elif hasattr(message, 'channel'):
       send_method = message.channel.send
   else:
       raise AttributeError(lm.get('message_send_error'))

   def split_code_block(lang: str, code_content: str) -> List[str]:
       """
       Split code content into chunks that fit within Discord's character limit.
       
       Args:
           lang: Programming language for syntax highlighting
           code_content: Code content to split
       
       Returns:
           List of code blocks with proper formatting
       """
       code_lines = code_content.split('\n')
       code_chunks = []
       current_chunk = ""

       for line in code_lines:
           if len(current_chunk) + len(line) + len(lang) + 10 > CHAR_LIMIT:
               code_chunks.append(current_chunk)
               current_chunk = line + "\n"
           else:
               current_chunk += line + "\n"
       
       if current_chunk:
           code_chunks.append(current_chunk)
       
       return [f"```{lang}\n{chunk}```" for chunk in code_chunks]

   def extract_thinking(response: str) -> Tuple[Optional[str], str]:
       """
       Extract thinking/reasoning content from the response.
       
       Args:
           response: Full response text
       
       Returns:
           Tuple of (thinking text, remaining response)
       """
       think_match = THINKING_PATTERN.search(response) or REASONING_PATTERN.search(response)
       if think_match:
           thinking_text = think_match.group(1).strip()
           response = think_match.re.sub('', response).strip()
           return thinking_text, response
       return None, response

   async def send_embed_message(thinking_text: str) -> None:
       """
       Send thinking content as an embed message.
       
       Args:
           thinking_text: Thinking content to send
       """
       for chunk in (thinking_text[i:i + EMBED_CHAR_LIMIT] for i in range(0, len(thinking_text), EMBED_CHAR_LIMIT)):
           embed = Embed(title=lm.get('message_ai_thinking'), description=chunk, color=0x3498db)
           await send_method(embed=embed)

   async def smart_send(content: str) -> None:
       """
       Smartly split and send content, handling code blocks and thinking content.
       
       Args:
           content: Content to send
       """
       thinking_text, response = extract_thinking(content)
       if thinking_text:
           await send_embed_message(thinking_text)

       blocks = re.split(r'(```(?:[a-zA-Z]+)?\n.*?```)', response, flags=re.DOTALL)
       current_chunk = ""
       messages_to_send = []

       for block in blocks:
           if (code_match := re.match(CODE_BLOCK_PATTERN, block, re.DOTALL)):
               lang, code_content = code_match.groups()
               for code_chunk in split_code_block(lang, code_content):
                   if len(current_chunk) + len(code_chunk) > CHAR_LIMIT:
                       messages_to_send.append(current_chunk)
                       current_chunk = code_chunk
                   else:
                       current_chunk += '\n' + code_chunk if current_chunk else code_chunk
           else:
               for line in block.split('\n'):
                   if len(current_chunk) + len(line) > CHAR_LIMIT:
                       messages_to_send.append(current_chunk)
                       current_chunk = line
                   else:
                       current_chunk += '\n' + line if current_chunk else line
       
       if current_chunk:
           messages_to_send.append(current_chunk)
       
       for msg in messages_to_send:
           await send_method(msg)

   await smart_send(response)
