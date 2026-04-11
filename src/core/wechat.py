import hashlib
import time
import xml.etree.ElementTree as ET


def verify_wechat_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    if not token or not signature or not timestamp or not nonce:
        return False
    parts = sorted([token, timestamp, nonce])
    expected = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
    return expected == signature


def parse_wechat_xml(raw: bytes) -> dict[str, str]:
    root = ET.fromstring(raw)
    data: dict[str, str] = {}
    for child in root:
        data[child.tag] = (child.text or "").strip()
    return data


def build_wechat_text_reply(to_user: str, from_user: str, content: str) -> str:
    root = ET.Element("xml")
    ET.SubElement(root, "ToUserName").text = to_user
    ET.SubElement(root, "FromUserName").text = from_user
    ET.SubElement(root, "CreateTime").text = str(int(time.time()))
    ET.SubElement(root, "MsgType").text = "text"
    ET.SubElement(root, "Content").text = content
    return ET.tostring(root, encoding="utf-8").decode("utf-8")

