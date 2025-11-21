import os
from typing import Tuple, Dict

import numpy as np
import pandas as pd

# 可选绘图
HAS_PLOT = True
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
except Exception:
    HAS_PLOT = False


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def load_data(path: str = "data/原始数据.csv") -> pd.DataFrame:
    """读取数据并解析 datetime 列为索引"""
    df = pd.read_csv(path)
    # 兼容不同列名：优先 'datetime'，否则猜测
    dt_col = None
    for c in df.columns:
        if c.lower() in ("datetime", "date", "time", "timestamp") or "date" in c.lower() or "time" in c.lower():
            dt_col = c
            break
    if dt_col is None:
        raise ValueError("未找到日期时间列，请确认文件包含 'datetime' 或类似列。")
    df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
    df = df.dropna(subset=[dt_col]).sort_values(dt_col).drop_duplicates(subset=[dt_col])
    df = df.set_index(dt_col)

    # 只保留数值测站列
    value_cols = df.select_dtypes(include="number").columns.tolist()
    if not value_cols:
        raise ValueError("未找到数值列。")
    return df[value_cols]


def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    miss = df.isna().sum().to_frame("missing_count")
    miss["missing_rate"] = (miss["missing_count"] / len(df)).round(4)
    return miss.sort_values("missing_count", ascending=False)


def resample_frames(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """统一到小时频率并生成按天均值"""
    hourly = df.resample("1H").mean()
    daily = hourly.resample("1D").mean()
    return hourly, daily


def impute_variants(hourly: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """两种常见填充：前向后向填充；时间插值"""
    ffill_bfill = hourly.ffill().bfill()
    interp = hourly.interpolate(method="time", limit_direction="both")
    return {"ffill_bfill": ffill_bfill, "interpolate_time": interp}


def iqr_clip(daily: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """IQR 异常值标注与裁剪（基于日均值，较稳健）"""
    flags = pd.DataFrame(index=daily.index)
    clipped = daily.copy()
    for c in daily.columns:
        s = daily[c].dropna()
        if s.empty:
            flags[c] = False
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flags[c] = (daily[c] < lo) | (daily[c] > hi)
        clipped[c] = daily[c].clip(lo, hi)
    return flags, clipped


def rolling_stats(hourly: pd.DataFrame) -> pd.DataFrame:
    """24 小时滚动均值与标准差"""
    roll_mean = hourly.rolling("24H", min_periods=6).mean().add_suffix("_roll24_mean")
    roll_std = hourly.rolling("24H", min_periods=6).std().add_suffix("_roll24_std")
    return pd.concat([roll_mean, roll_std], axis=1)


def hour_of_day_pattern(hourly: pd.DataFrame) -> pd.DataFrame:
    """按小时（0-23）聚合平均，查看日内模式"""
    df = hourly.copy()
    df["hour"] = df.index.hour
    return df.groupby("hour").mean(numeric_only=True)


def lag_correlation(hourly: pd.DataFrame, max_lag: int = 24) -> pd.DataFrame:
    """计算两两测站在 ±max_lag 小时范围的最大滞后相关"""
    cols = hourly.columns.tolist()
    results = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = hourly[cols[i]], hourly[cols[j]]
            best = (None, -np.inf)
            for lag in range(-max_lag, max_lag + 1):
                if lag < 0:
                    corr = a.shift(-lag).corr(b)
                else:
                    corr = a.corr(b.shift(lag))
                if corr is not None and not np.isnan(corr) and corr > best[1]:
                    best = (lag, corr)
            results.append({"pair": f"{cols[i]}~{cols[j]}", "best_lag_h": best[0], "corr": round(best[1], 4)})
    return pd.DataFrame(results).sort_values("corr", ascending=False)


def plots(hourly: pd.DataFrame, daily: pd.DataFrame, out_dir: str):
    if not HAS_PLOT:
        print("未安装 matplotlib/seaborn，跳过图表。可运行: conda install -y matplotlib seaborn")
        return

    sns.set_theme(style="whitegrid")

    # 时序曲线（小时）
    plt.figure(figsize=(10, 4))
    for c in hourly.columns:
        plt.plot(hourly.index, hourly[c], lw=0.8, label=c)
    plt.title("各测站 NO2 小时浓度")
    plt.xlabel("time"); plt.ylabel("value")
    plt.legend(ncol=3, fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "ts_hourly.png"), dpi=150)
    plt.close()

    # 日均曲线
    plt.figure(figsize=(10, 4))
    for c in daily.columns:
        plt.plot(daily.index, daily[c], lw=1.2, label=c)
    plt.title("各测站 NO2 日均")
    plt.xlabel("date"); plt.ylabel("value")
    plt.legend(ncol=3, fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "ts_daily.png"), dpi=150)
    plt.close()

    # 相关性热力图（小时）
    corr = hourly.corr(numeric_only=True)
    plt.figure(figsize=(4, 3))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="Blues")
    plt.title("站点相关性（小时）")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "corr_heatmap.png"), dpi=150)
    plt.close()


def main():
    pd.set_option("display.max_columns", 100)
    out_dir = "output"
    ensure_dir(out_dir)

    # 1) 读取与基础信息
    df = load_data("data/原始数据.csv")
    print("数据时间范围:", df.index.min(), "→", df.index.max())
    print("列名:", df.columns.tolist())
    miss = missing_report(df)
    print("\n缺失值统计（前 10 行）:\n", miss.head(10))

    # 2) 统一频率与聚合
    hourly, daily = resample_frames(df)

    # 3) 两种填充方案
    imputed = impute_variants(hourly)
    imputed["ffill_bfill"].to_csv(os.path.join(out_dir, "imputed_ffill_bfill_hourly.csv"), encoding="utf-8-sig")
    imputed["interpolate_time"].to_csv(os.path.join(out_dir, "imputed_interpolate_hourly.csv"), encoding="utf-8-sig")

    # 4) 异常值（基于日均值）
    flags, clipped = iqr_clip(daily)
    flags.to_csv(os.path.join(out_dir, "outlier_flags_daily.csv"), encoding="utf-8-sig")
    clipped.to_csv(os.path.join(out_dir, "daily_clipped.csv"), encoding="utf-8-sig")
    print("\n异常值天数统计:\n", flags.sum())

    # 5) 滚动统计（小时）
    roll = rolling_stats(imputed["interpolate_time"])
    roll.to_csv(os.path.join(out_dir, "rolling_24h_stats.csv"), encoding="utf-8-sig")

    # 6) 日内模式
    hod = hour_of_day_pattern(imputed["interpolate_time"])
    hod.to_csv(os.path.join(out_dir, "hour_of_day_mean.csv"), encoding="utf-8-sig")

    # 7) 相关与滞后相关
    corr_hourly = hourly.corr(numeric_only=True)
    corr_hourly.to_csv(os.path.join(out_dir, "corr_hourly.csv"), encoding="utf-8-sig")
    lag_df = lag_correlation(imputed["interpolate_time"], max_lag=24)
    lag_df.to_csv(os.path.join(out_dir, "best_lag_corr.csv"), index=False, encoding="utf-8-sig")
    print("\n滞后相关（Top 5）:\n", lag_df.head())

    # 8) 导出关键汇总
    daily.to_csv(os.path.join(out_dir, "daily_mean.csv"), encoding="utf-8-sig")
    miss.to_csv(os.path.join(out_dir, "missing_report.csv"), encoding="utf-8-sig")

    # 9) 可视化
    plots(imputed["interpolate_time"], daily, out_dir)

    print(f"\n分析完成。结果已保存到: {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()