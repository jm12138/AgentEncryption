# Author: Acer Zhang
# Datetime: 2021/10/27
# Copyright belongs to the author.
# Please indicate the source for reprinting.
import os
import math
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

    def encode(self, input: any, output: str, export: str = None, ratio: float = 0.1, check: bool = True) -> dict:
        '''
        加密函数

        :param 
            input(any): 输入的需要加密的数据
            output(str: None): 输出的文件路径名称（无需文件后缀）
            export(str: None): 导出密钥等私密参数的路径名称（无需文件后缀），默认返回但不导出文件
            ratio(float: 0.1 [0 < ratio <= 1]): 加密数据比例，数值越大加密的数据比例越大，1 表示完全加密
            check(bool: True): 检测加密数据是否可以正常解密

        :return
            private_params(dict): 加密器的私密参数，如密钥等

        :format details
            json: 此格式支持如下几种数据类型 (dict, list, str, int, float, bool, None, bytes->bytes_str, tuple(must -> list))
        '''
        assert 0 < ratio <= 1, 'Please check the ratio.'

        bytes_datas = json.dumps(
            Encryptor.check_and_convert(input)).encode('UTF-8')
        spilt_length = math.ceil(len(bytes_datas) * ratio)
        encrypt_datas = self.encrypt_op.encode(
            bytes_datas[:spilt_length]
        )
        length = len(encrypt_datas)
        encrypt_datas = encrypt_datas + bytes_datas[spilt_length:]

        with open(f'{output}.json', "w") as file:
            json.dump({
                'datas': Encryptor.bytes2str(encrypt_datas),
                'params': Encryptor.check_and_convert(self.encrypt_op.get_public_params()),
                'length': length
            }, file)

        private_params = self.encrypt_op.get_private_params(export)

        if check:
            _input = Encryptor.decode(
                input=f'{output}.json',
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
        file_name, ext = os.path.splitext(input)
        if ext == '':
            ext = '.json'
        file_path = file_name + ext

        # 加载加密数据包
        with open(file_path, "r") as file:
            encrypt_package = json.load(file)

        # 解码公开参数
        params = encrypt_package['params']
        params = Encryptor.resume_and_convert(params)

        # 解码加密长度信息
        length = encrypt_package['length']

        # 解码加密数据
        encrypt_datas = Encryptor.str2bytes(encrypt_package['datas'])
        decode = encrypt_package.get('decode', decode)
        pure_datas = decode(encrypt_datas[:length], **kwargs, **params)
        pure_datas = pure_datas + encrypt_datas[length:]

        # 重新加载原始数据
        output = json.loads(pure_datas.decode('UTF-8'))
        output = Encryptor.resume_and_convert(output)

        return output
