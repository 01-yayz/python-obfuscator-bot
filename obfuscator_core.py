"""
Core Obfuscator Module
"""

import os
import base64
import zlib
import random
import string
import ast
import marshal
import hashlib
import json
from datetime import datetime
from typing import Dict, List
import itertools

class PythonObfuscator:
    def __init__(self):
        self.obfuscation_level = 3
        
    def obfuscate_code(self, code: str, level: int = 3) -> str:
        self.obfuscation_level = level
        
        if level >= 1:
            code = self._rename_variables(code)
        
        if level >= 2:
            code = self._encode_strings(code)
        
        if level >= 3:
            code = self._compile_to_bytecode(code)
        
        return code
    
    def _rename_variables(self, code: str) -> str:
        try:
            tree = ast.parse(code)
            var_map = {}
            counter = 1
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id not in dir(__builtins__):
                    if node.id not in var_map:
                        new_name = f"var_{counter:04d}"
                        var_map[node.id] = new_name
                        counter += 1
                    node.id = var_map[node.id]
            
            return ast.unparse(tree)
        except:
            return code
    
    def _encode_strings(self, code: str) -> str:
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    encoded = base64.b64encode(node.value.encode()).decode()
                    replacement = f"__import__('base64').b64decode('{encoded}').decode()"
                    
                    new_node = ast.parse(replacement, mode='eval').body
                    node.value = None
                    node = new_node
            
            return ast.unparse(tree)
        except:
            return code
    
    def _compile_to_bytecode(self, code: str) -> str:
        try:
            compiled = compile(code, '<string>', 'exec')
            marshaled = marshal.dumps(compiled)
            encoded = base64.b64encode(marshaled).decode()
            
            loader = f"""
import marshal, base64
exec(marshal.loads(base64.b64decode('{encoded}')))
"""
            return loader.strip()
        except:
            return code

class FileObfuscator:
    def __init__(self):
        self.code_obf = PythonObfuscator()
    
    def obfuscate_file(self, input_file: str, output_file: str = None, level: int = 2) -> str:
        if not output_file:
            base_name = os.path.basename(input_file)
            name, ext = os.path.splitext(base_name)
            output_file = f"{name}_obf_l{level}{ext}"
        
        with open(input_file, 'r', encoding='utf-8') as f:
            code = f.read()
        
        obfuscated_code = self.code_obf.obfuscate_code(code, level)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(obfuscated_code)
        
        return output_file

class AdvancedObfuscator:
    @staticmethod
    def multi_layer_obfuscate(code: str, layers: int = 3) -> str:
        current_code = code
        
        for i in range(layers):
            # XOR encryption
            key = random.choice(['secret', 'password', 'key123'])
            xor_bytes = bytes(ord(c) ^ ord(key[j % len(key)]) 
                            for j, c in enumerate(current_code))
            current_code = base64.b64encode(xor_bytes).decode()
        
        decoder = f"""
import base64
def decode(data):
    keys = ['secret', 'password', 'key123']
    for key in reversed(keys[:{layers}]):
        data = base64.b64decode(data)
        data = bytes(b ^ ord(key[i % len(key)]) for i, b in enumerate(data))
    return data.decode()

exec(decode('{current_code}'))
"""
        return decoder
