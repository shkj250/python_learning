import os
import pandas as pd

# 下载数据（如果网络慢，我有备用方案）
url = "https://raw.githubusercontent.com/pandas-dev/pandas/main/doc/data/air_quality_no2.csv"
try:
    df = pd.read_csv(url)
    print("✅ 数据下载成功！")
except Exception as e:
    print("⚠️ 下载失败，用备用方案...", str(e))
    # 备用：尝试读取本地已下载的文件（如果存在），否则创建一个空的 DataFrame
    local_path = "data/原始数据.csv"
    if os.path.exists(local_path):
        df = pd.read_csv(local_path)
        print("✅ 从本地文件加载数据：", local_path)
    else:
        print("⚠️ 本地备用文件不存在，创建空的 DataFrame")
        df = pd.DataFrame()

# 看一眼数据
print("数据形状:", df.shape)
print("\n前5行:\n", df.head())

# 确保保存目录存在再保存
os.makedirs("data", exist_ok=True)
df.to_csv("data/原始数据.csv", index=False)
# 三问：有什么？是什么？干净吗？
print("📌 列名:", df.columns.tolist())
print("\n📌 数据类型:\n", df.dtypes)
print("\n📌 缺失值统计:\n", df.isna().sum())
print("\n📌 描述统计:\n", df.describe())