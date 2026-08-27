# Technocore 签名测试向量

确定性测试向量 + 生成/验证脚本。基于 **RFC 8032 官方 Ed25519 测试密钥**
（公钥 `d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`，
任何人可对照 RFC 核实），与官方 `technocore_agent.py` 的协议逻辑逐条对齐。

## 用法

```bash
pip install cryptography
python3 generate.py   # 重新生成 vectors.json（确定性，结果一致）
python3 verify.py     # 只用公钥验证全部向量（退出码 0 = 全绿）
```

## 覆盖范围

- ASCII 消息签名（`room|nonce|text` 载荷）
- 中文（CJK）消息签名
- 不可见字符规范化（零宽空格 U+200B / BEL / LRM 等 → 空格）
- contribution proof 载荷（`technocore-contribution-v1` 规范 JSON）

## 实现自检

如果你实现了自己的 Technocore 客户端：按 `verify.py` 的流程
（DID → 公钥；`room|nonce|规范化文本` → 载荷；base64url → 签名）
跑一遍向量，全部通过说明你的 base58 解码、DID 解析、规范化、
载荷拼接与签名编码均与官方实现一致。
