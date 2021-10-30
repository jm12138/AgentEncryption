# Author: Acer Zhang
# Datetime: 2021/10/27
# Copyright belongs to the author.
# Please indicate the source for reprinting.
import os
import json
import base64
import pickle

from agentenc.ops import EncryptOp


class Encryptor:
    def __init__(self, encrypt_op: EncryptOp):
        """
        加密器基类

        :param 
            encrypt_op(EncryptOp): 加密相关OP
        """
        self.encrypt_op = encrypt_op

    @staticmethod
    def bytes2str(input: bytes) -> str:
        '''
        bytes to base64 str (input -> data:data/agt;base64,{base64[input]})

        :param 
            input(bytes): 输入

        :return
            output(str): 输出 
        '''
        output = base64.b64encode(input).decode('UTF-8')
        return f'data:data/agt;base64,{output}'

    @staticmethod
    def str2bytes(input: str) -> bytes:
        '''
        base64 str to bytes (data:data/agt;base64,{base64[input]} -> input)

        :param 
            input(bytes): 输入

        :return
            output(str): 输出
        '''
        if isinstance(input, str) and input[:21] == 'data:data/agt;base64,':
            input = base64.b64decode(input[21:].encode('UTF-8'))
            assert type(input) == bytes, "Decode error!"
        return input

    @staticmethod
    def check_and_convert(input: any) -> any:
        '''
        检查并递归转换 bytes -> bytes_str

        :param 
            input(any): 输入

        :return
            output(any): 输出
        '''
        if isinstance(input, dict):
            _input = {}
            for k in input.keys():
                _input[k] = Encryptor.check_and_convert(input[k])
            return _input
        elif isinstance(input, list):
            _input = []
            for i in range(len(input)):
                _input.append(Encryptor.check_and_convert(input[i]))
            return _input
        elif isinstance(input, tuple):
            raise ValueError(
                f'Please convert tuple input {input} to list type.')
        elif isinstance(input, bytes):
            return Encryptor.bytes2str(input)
        elif isinstance(input, (str, int, float, bool)) or input is None:
            return input
        else:
            raise ValueError('Please check input data type.')

    @staticmethod
    def resume_and_convert(input: any) -> any:
        '''
        恢复并递归转换 bytes_str -> bytes

        :param 
            input(any): 输入

        :return
            output(any): 输出
        '''
        if isinstance(input, dict):
            for k in input.keys():
                input[k] = Encryptor.resume_and_convert(input[k])
            return input
        elif isinstance(input, list):
            for i in range(len(input)):
                input[i] = Encryptor.resume_and_convert(input[i])
            return input
        elif isinstance(input, str):
            return Encryptor.str2bytes(input)
        elif isinstance(input, (int, float, bool)) or input is None:
            return input
        else:
            raise ValueError('Please check input data type.')

    def encode(self, input: any, output: str = None, format: str = 'pkl', export: str = None, check: bool = True) -> dict:
        '''
        加密函数

        :param 
            input(any): 输入的需要加密的数据
            output(str: None): 输出的文件路径名称（无需文件后缀），默认为 {input}.{format}
            format(str: pkl [pkl / json]): 输出的数据格式
            export(str: None): 导出密钥等私密参数的路径名称（无需文件后缀），默认返回但不导出文件
            check(bool: True): 检测加密数据是否可以正常解密

        :return
            private_params(dict): 加密器的私密参数，如密钥等

        :format details
            pkl: 此格式支持的加密数据类型较多，并且附带 python 解密函数，可依靠自身进行解密，但只可以在 python 端进行解密操作
            json: 此格式支持如下几种数据类型 (dict, list, str, int, float, bool, None, bytes->bytes_str, tuple(must -> list)), 可以在任意语言中读取和解密，需搭配对应语言的解密函数进行解密操作
        '''
        if output is None:
            output = input

        if format == 'pkl':
            encrypt_datas = self.encrypt_op.encode(
                pickle.dumps(input, protocol=4))

            with open(f'{output}.{format}', "wb") as file:
                pickle.dump({
                    'datas': Encryptor.bytes2str(encrypt_datas),
                    'params': Encryptor.check_and_convert(self.encrypt_op.get_public_params()),
                    'decode': self.encrypt_op.decode
                }, file, protocol=4)

        elif format == 'json':
            encrypt_datas = self.encrypt_op.encode(
                json.dumps(Encryptor.check_and_convert(input)).encode('UTF-8'))

            with open(f'{output}.{format}', "w") as file:
                json.dump({
                    'datas': Encryptor.bytes2str(encrypt_datas),
                    'params': Encryptor.check_and_convert(self.encrypt_op.get_public_params())
                }, file)
        else:
            raise ValueError('Please check the format type.')

        private_params = self.encrypt_op.get_private_params(export)

        if check:
            _input = Encryptor.decode(
                input=f'{output}.{format}',
                decode=self.encrypt_op.decode,
                **private_params
            )
            assert _input == input, "Encryption check error!"

        return private_params

    @staticmethod
    def decode(input: str, decode=None, **kwargs) -> any:
        '''
        解密函数

        :param 
            input(str): 输入的文件路径
            decode(func): 解密函数 
            **kwargs: 解密所需的一些其他参数

        :return
            pure_datas(any): 原始数据
        '''
        ext = os.path.splitext(input)[1]

        # 加载机密数据包
        if ext == '.pkl':
            with open(input, "rb") as file:
                encrypt_package = pickle.load(file)
        elif ext == '.json':
            with open(input, "r") as file:
                encrypt_package = json.load(file)
        else:
            raise ValueError('Please check input path.')

        # 解码公开参数
        params = encrypt_package['params']
        params = Encryptor.resume_and_convert(params)

        # 解码加密数据
        encrypt_datas = Encryptor.str2bytes(encrypt_package['datas'])
        decode = encrypt_package.get('decode', decode)
        pure_datas = decode(encrypt_datas, **kwargs, **params)

        # 重新加载原始数据
        if ext == '.pkl':
            output = pickle.loads(pure_datas)
        elif ext == '.json':
            output = json.loads(pure_datas.decode('UTF-8'))
            output = Encryptor.resume_and_convert(output)
        else:
            raise ValueError('Please check input data type.')

        return output
