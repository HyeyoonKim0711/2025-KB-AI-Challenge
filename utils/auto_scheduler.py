import schedule
import time
import os
from datetime import datetime
from utils.update_finance_products import update_fss, update_monthly
from utils.update_support_products import update_support_projects


# 로그 폴더 생성
os.makedirs("logs", exist_ok=True)


### 금융상품
def run_fss_job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{now}] ▶ FSS 업데이트 시작")
        update_fss()
        with open("logs/fss_crawl_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] FSS 업데이트 성공\n{'='*60}\n")
    except Exception as e:
        with open("logs/fss_crawl_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] FSS 업데이트 실패: {e}\n{'='*60}\n")

def run_kinfa_job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{now}] ▶ KINFA 업데이트 시작")
        update_monthly() 
        with open("logs/kinfa_crawl_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] KINFA 업데이트 성공\n{'='*60}\n")
    except Exception as e:
        with open("logs/kinfa_crawl_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] KINFA 업데이트 실패: {e}\n{'='*60}\n")

### 지원사업
def run_support_job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{now}] ▶ 지원사업 업데이트 시작")
        update_support_projects()
        with open("logs/support_crawl_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] 지원사업 업데이트 성공\n{'='*60}\n")
    except Exception as e:
        with open("logs/support_crawl_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] 지원사업 업데이트 실패: {e}\n{'='*60}\n")


# 매일 자정에 1일이면 실행
def check_first_day_of_month():
    if datetime.today().day == 1:
        run_kinfa_job()

# 운영용 스케줄
schedule.every().monday.at("08:00").do(run_fss_job)
schedule.every().day.at("00:00").do(check_first_day_of_month)
schedule.every().day.at("00:00").do(run_support_job)


print("크롤링 자동 스케줄러 시작됨")
print(" - FSS : 매주 월요일 08시")
print(" - KINFA : 매달 1일 00시")

# 실제 실행 루프
while True:
    schedule.run_pending()
    time.sleep(60)

