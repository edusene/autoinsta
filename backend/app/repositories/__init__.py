"""Camada de acesso a dados: apenas SQL parametrizado, sem regra de negócio.

Toda função recebe a conexão (transação) como primeiro argumento.
Funções que expõem dados de usuário SEMPRE filtram por user_id.
"""
