import base64
import re

def voe_decrypt(scrambled, key):
    # 1. Reverse
    scrambled = scrambled[::-1]
    
    # 2. Substitution mapping for numbers
    mapping = {'!': '0', '@': '1', '#': '2', '&': '3', '%': '4', '?': '5', '~': '6', '*': '7', '^': '8', '$': '9'}
    for k, v in mapping.items():
        scrambled = scrambled.replace(k, v)
    
    # 3. Custom Base64 alphabet (VOE swaps a-z and A-Z)
    std_b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    voe_b64 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/"
    
    # Translate from VOE alphabet to standard
    trans = str.maketrans(voe_b64, std_b64)
    translated = scrambled.translate(trans)
    
    # 4. Base64 decode
    try:
        decoded_bytes = base64.b64decode(translated + "===") # Add padding just in case
        
        # 5. XOR with key
        res = ""
        for i, b in enumerate(decoded_bytes):
            res += chr(b ^ ord(key[i % len(key)]))
        return res
    except Exception as e:
        return f"FAILED: {e}"

# Test data from user's page
scrambled = "CR1J#&MKyE*~pR8m@$JIcq#&sSH2@$Mz9E!!pTIi~@omIp^^sH" # Truncated
# Key from window.c...
key = "f98a024e"

# Real string from grep L252 earlier:
# ["DROH#&nJjm#&AJIg!!BRMa%?o1yj~@MwAE#&J11g%?BScq^^p1R1*~MzgE~@AIki~@GIcq!!sR1f~@HzkL~@JzIe..."]
full_scrambled = "DROH#&nJjm#&AJIg!!BRMa%?o1yj~@MwAE#&J11g%?BScq^^p1R1*~MzgE~@AIki~@GIcq!!sR1f~@HzkL~@JzIe" # Part of it

print(f"Decrypted: {voe_decrypt(full_scrambled, key)}")
