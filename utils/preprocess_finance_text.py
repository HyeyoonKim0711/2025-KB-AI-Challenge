import json
import os
import re
from typing import Union, List


# 값 누락 확인
def is_missing(value: Union[str, List]) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "-":
        return True
    return False

# 파일명 안전하게 정리
def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^\w가-힣]", "", s)
    return s[:30]

# 대출부대비용 등 일반 리스트 → 문장 처리
def format_list_to_sentences(items: List[str]) -> List[str]:
    formatted = []
    for item in items:
        item = item.lstrip("-").strip()
        if ":" in item:
            key, value = item.split(":", 1)
            sentence = f"{key.strip()}는 {value.strip()}"
        else:
            sentence = item

        if sentence.endswith("니다.") or sentence.endswith("다."):
            formatted.append(sentence)
        else:
            formatted.append(sentence + "입니다.")
    return formatted

# 중도상환 수수료 특수 처리
def format_prepayment_fee_sentences(items: List[str]) -> List[str]:
    result = []
    for item in items:
        item = item.strip()
        if any(op in item for op in ["X", "x", "÷", "*", "="]):
            result.append(f'"{item}"으로 계산됩니다.')
        elif "최장" in item or "발생" in item:
            result.append(item if item.endswith("다.") else item + "합니다.")
        elif "수수료율" in item:
            result.append("수수료율은 다음과 같습니다.")
        elif item.startswith("-"):
            try:
                title, value = item.lstrip("-").strip().split(":", 1)
                result.append(f"{title.strip()}의 수수료율은 {value.strip()}입니다.")
            except ValueError:
                sentence = item.lstrip("-").strip()
                result.append(sentence if sentence.endswith("니다.") or sentence.endswith("다.") else sentence + "입니다.")
        else:
            result.append(item if item.endswith("니다.") or item.endswith("다.") else item + "입니다.")
    return result

# 전체 상품 정보를 문장으로 변환
def convert_loan_json_to_text(data):
    lines = [f"{data['금융회사']}에서 '{data['상품명']}' 상품을 제공합니다."]
    lines.append(f"자금용도는 {data['자금용도']}입니다.")
    lines.append(f"대출 종류는 {data['대출종류']}입니다.")
    lines.append(f"금리 방식은 {data['금리방식']}입니다.")
    lines.append(f"상환 방식은 {data['상환방식']}입니다.")
    lines.append(f"가입 대상은 {data['가입대상']}입니다.")

    if not is_missing(data.get("가입대상 세부요건")):
        lines.append(f"구체적인 가입 요건은 '{data['가입대상 세부요건']}'입니다.")

    if not is_missing(data.get("전월 평균금리")):
        lines.append(f"전월 평균금리는 {data['전월 평균금리']}입니다.")
    else:
        lines.append("전월 평균금리는 제공되지 않았습니다.")

    if isinstance(data.get("적용가능 금리"), list) and len(data["적용가능 금리"]) == 2:
        최고금리 = data["적용가능 금리"][0].split(": ")[1]
        최저금리 = data["적용가능 금리"][1].split(": ")[1]
        lines.append(f"적용 가능 금리는 최고 {최고금리}, 최저 {최저금리}입니다.")

    if not is_missing(data.get("대출한도")):
        lines.append(f"대출 한도는 {data['대출한도']}입니다.")

    if not is_missing(data.get("우대금리")):
        lines.append(f"우대금리는 {data['우대금리']}입니다.")

    if not is_missing(data.get("가입방법")):
        lines.append(f"가입은 {data['가입방법']}을 통해 가능합니다.")

    수수료 = data.get("중도상환 수수료")
    if 수수료 and not is_missing(수수료):
        lines.append("중도상환 수수료는 다음과 같습니다.")
        if isinstance(수수료, list):
            lines.extend(format_prepayment_fee_sentences(수수료))
        else:
            lines.append(f"{수수료}입니다.")

    비용 = data.get("대출부대비용")
    if 비용 and not is_missing(비용):
        lines.append("대출 부대비용은 다음과 같습니다.")
        if isinstance(비용, list):
            lines.extend(format_list_to_sentences(비용))
        else:
            lines.append(f"{비용} 등이 포함됩니다.")

    연체 = data.get("연체이자율")
    if 연체 and not is_missing(연체):
        if isinstance(연체, list):
            lines.append(f"연체 이자율은 {' '.join(연체)}입니다.")
        else:
            lines.append(f"연체 이자율은 {연체}입니다.")

    담당 = data.get("담당부서 및 연락처")
    if 담당 and not is_missing(담당):
        lines.append("담당 부서 및 연락처는 다음과 같습니다.")
        if isinstance(담당, list):
            for d in 담당:
                d = d.strip()
                if d.endswith("니다.") or d.endswith("다."):
                    lines.append(d)
                else:
                    lines.append(f"{d}입니다.")
        else:
            d = 담당.strip()
            if d.endswith("니다.") or d.endswith("다."):
                lines.append(d)
            else:
                lines.append(f"{d}입니다.")

    # 줄바꿈 없이 문장 이어붙이기
    return " ".join(lines)

# 실행 함수
def process_fss_json_to_text(json_path: str, output_dir: str = None):
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if output_dir is None:
        output_dir = os.path.join(CURRENT_DIR, "data", "finance_products_txt")
    else:
        output_dir = os.path.join(CURRENT_DIR, output_dir)
        
    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    for idx, item in enumerate(items, start=1):
        금융회사 = sanitize_filename(item.get("금융회사", "unknown"))
        상품명 = sanitize_filename(item.get("상품명", f"상품_{idx}"))
        filename = f"fss_{str(idx).zfill(3)}_{금융회사}_{상품명}.txt"
        filepath = os.path.join(output_dir, filename)

        text = convert_loan_json_to_text(item)

        with open(filepath, "w", encoding="utf-8") as out:
            out.write(text)

        print(f"저장 완료: {filename}")


### JSON to txt for KINFA ###
def is_missing(value: Union[str, List]) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "-")

def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^\w가-힣]", "", s)
    return s[:30]

# 하나의 상품 정보를 자연어 문장으로 변환 
def convert_row_to_text(data: dict) -> str:
    lines = []

    lines.append(f"[{data['기준년월']}] 기준 정보입니다. {data['제공기관명']}에서 '{data['금융상품명']}' 상품을 제공합니다.")
    lines.append(f"상품명(내부 코드용)은 '{data['상품명']}'입니다. 운영기한은 {data['운영기한']}까지입니다.")
    lines.append(f"자금용도는 {data['용도']}이며, 대출 한도는 {data['대출한도']}입니다. 금리 구분은 {data['금리구분']}이며, 금리는 {data['금리']}입니다.")
    lines.append(f"상환 방식은 {data['상환방법']}이고, 가입 대상은 {data['대상']}입니다.")

    if not is_missing(data.get("지원대상 상세조건")):
        lines.append(f"지원 대상의 세부 조건은 '{data['지원대상 상세조건']}'입니다.")
    if not is_missing(data.get("신용등급")):
        lines.append(f"요구되는 신용등급은 {data['신용등급']}입니다.")
    if not is_missing(data.get("거주지역원금균등분할상환")):
        lines.append(f"거주 지역에 따른 원금균등분할상환 조건은 {data['거주지역원금균등분할상환']}입니다.")
    if not is_missing(data.get("우대금리/가산금리 조건")):
        lines.append(f"우대금리 또는 가산금리는 다음 조건에 따라 적용됩니다: {data['우대금리/가산금리 조건']}.")
    if not is_missing(data.get("연체이자율(연)")):
        lines.append(f"연체 시 적용되는 이자율은 연 {data['연체이자율(연)']}입니다.")
    if not is_missing(data.get("가입(신청)방법")):
        lines.append(f"가입 또는 신청은 '{data['가입(신청)방법']}'을 통해 가능합니다.")
    if not is_missing(data.get("연락처")):
        lines.append(f"추가 문의는 {data['연락처']}로 가능합니다.")
    if not is_missing(data.get("문의처 및 연락처")):
        lines.append(f"문의처 및 담당 부서는 다음과 같습니다: {data['문의처 및 연락처']}.")
    if not is_missing(data.get("관련 사이트")):
        lines.append(f"자세한 정보는 다음 관련 사이트에서도 확인할 수 있습니다: {data['관련 사이트']}.")
    if not is_missing(data.get("대상_필터")):
        lines.append(f"이 상품은 '{data['대상_필터']}'에 해당하는 분들을 위한 상품입니다.")
    if not is_missing(data.get("취급기관_상세보기용")):
        lines.append(f"해당 상품은 '{data['취급기관_상세보기용']}'에서 취급합니다.")
    if not is_missing(data.get("상품존재여부")):
        존재여부 = "존재합니다" if 'Y' in data['상품존재여부'] else "존재하지 않습니다"
        lines.append(f"해당 상품은 현재 {존재여부}.")

    return " ".join(lines) 

# JSON → TXT 저장 
def process_kinfa_json_to_text(json_path: str, output_dir: str = None):
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if output_dir is None:
        output_dir = os.path.join(CURRENT_DIR, "data", "finance_products_txt")
    else:
        output_dir = os.path.join(CURRENT_DIR, output_dir)
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = [data]

    os.makedirs(output_dir, exist_ok=True)

    for idx, row_dict in enumerate(data):
        기관명 = sanitize_filename(str(row_dict.get("제공기관명", "unknown")))
        상품명 = sanitize_filename(str(row_dict.get("금융상품명", f"상품_{idx}")))

        filename = f"kinfa_{str(idx+1).zfill(3)}_{기관명}_{상품명}.txt"
        filepath = os.path.join(output_dir, filename)

        text = convert_row_to_text(row_dict)

        with open(filepath, "w", encoding="utf-8") as out:
            out.write(text)

        print(f"저장 완료: {filename}")


def main():
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(CURRENT_DIR, "data")

    fss_json_path = os.path.join(DATA_DIR, "fss_products.json")
    kinfa_json_path = os.path.join(DATA_DIR, "kinfa_products.json")

    process_fss_json_to_text(fss_json_path)
    process_kinfa_json_to_text(kinfa_json_path)

if __name__ == "__main__":
    main()
