"""Two-page client-style factsheet for the v2 strategy, with v1 shown as the research history."""
import pandas as pd, numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether)
from config import OUT, FIG

NAVY = colors.HexColor("#0B3D91"); GREY = colors.HexColor("#5B6770"); LIGHT = colors.HexColor("#EEF2F7")
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, textColor=NAVY, leading=20)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, textColor=NAVY, spaceBefore=8, spaceAfter=3)
SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=9, textColor=GREY, leading=12)
BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=8.3, leading=10.8, textColor=colors.black)
SMALL = ParagraphStyle("s", fontName="Helvetica", fontSize=7.2, leading=9.2, textColor=GREY)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=9, bulletIndent=0, spaceAfter=1.5)

def pct(x, d=1): return f"{x*100:+.{d}f}%" if x < 0 or True else ""
def p(x, d=1): return f"{x*100:.{d}f}%"

def tbl(data, widths, header=True, zebra=True, align_right_from=1):
    t = Table(data, colWidths=widths)
    st = [("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
          ("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
          ("LINEBELOW", (0, -1), (-1, -1), 0.6, NAVY)]
    if header:
        st += [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == 0: st.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(st)); return t

def build():
    v2 = pd.read_parquet(OUT / "returns_v2_betaneutral.parquet"); v1 = pd.read_parquet(OUT / "returns_multifactor.parquet")
    m2 = pd.read_csv(OUT / "metrics_v2_betaneutral.csv", index_col=0).iloc[:, 0]
    m1 = pd.read_csv(OUT / "metrics.csv", index_col=0).iloc[:, 0]
    cal = pd.read_csv(OUT / "calendar_v2_betaneutral.csv", index_col=0)
    st = pd.read_csv(OUT / "stress_v2_betaneutral.csv", index_col=0)
    reg = pd.read_csv(OUT / "ff_regression_v2_betaneutral.csv", index_col=0)
    r2 = pd.read_csv(OUT / "ff_r2_v2_betaneutral.csv", index_col=0).iloc[0, 0]
    boot = pd.read_csv(OUT / "bootstrap_v2_betaneutral.csv", index_col=0).iloc[:, 0]
    boot1 = pd.read_csv(OUT / "bootstrap_multifactor.csv", index_col=0).iloc[:, 0]
    split = pd.read_csv(OUT / "split_sample.csv", index_col=0)
    start, end = v2.index[0].strftime("%b %Y"), v2.index[-1].strftime("%b %Y")

    doc = SimpleDocTemplate(str(OUT / "Factsheet_MultiFactor_US_LargeCap.pdf"), pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch, topMargin=0.5*inch, bottomMargin=0.45*inch,
                            title="Multi-Factor US Large Cap Strategy - Factsheet", author="Hugo Hoenn")
    W = letter[0] - 1.2*inch
    S = []
    # ---------- Page 1 ----------
    hdr = Table([[Paragraph("Multi-Factor US Large Cap Equity Strategy", H1),
                  Paragraph(f"Research factsheet &nbsp;|&nbsp; Backtest {start} - {end} &nbsp;|&nbsp; Hugo Hoenn", SUB)]],
                colWidths=[W*0.55, W*0.45])
    hdr.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                             ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY), ("BOTTOMPADDING", (0, 0), (-1, 0), 5)]))
    S += [hdr, Spacer(1, 6)]
    S.append(Paragraph(
        "<b>Objective.</b> Outperform a cap-weighted US large-cap benchmark by modest, consistent amounts through a systematic, "
        "long-only tilt toward stocks with attractive <b>value</b>, <b>momentum</b> and <b>quality</b> characteristics, "
        "while holding market beta, sector weights and turnover close to the benchmark. The strategy is designed as a "
        "smart-beta building block: transparent rules, low cost, and factor exposures that can be explained to a client in one page.", BODY))
    S.append(Spacer(1, 5))
    # KPI strip
    kpi = [["Excess return (ann.)", "Information ratio", "Tracking error", "Sharpe (bench.)", "Beta", "Max drawdown (bench.)", "1-way turnover"],
           [pct(m2["Excess return"]), f"{m2['Information ratio']:.2f}", p(m2["Tracking error"]),
            f"{m2['Sharpe']:.2f} ({m2['Benchmark Sharpe']:.2f})", f"{m2['Beta']:.2f}",
            f"{p(m2['Max drawdown'])} ({p(m2['Benchmark max drawdown'])})", f"{p(v2.turnover.mean())}/mo"]]
    k = Table(kpi, colWidths=[W/7]*7)
    k.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica", 7), ("TEXTCOLOR", (0, 0), (-1, 0), GREY),
                           ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 12), ("TEXTCOLOR", (0, 1), (-1, 1), NAVY),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    S += [k, Spacer(1, 6)]
    # growth + relative charts side by side
    imgs = Table([[Image(str(FIG / "growth_v2_betaneutral.png"), width=W*0.5-4, height=(W*0.5-4)*4.2/9),
                   Image(str(FIG / "relative_drawdown_v2_betaneutral.png"), width=W*0.5-4, height=(W*0.5-4)*5.5/9)]],
                 colWidths=[W*0.5, W*0.5])
    imgs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    S.append(imgs)
    # performance table + calendar side by side
    perf = [["", "Strategy", "Benchmark", "Active"],
            ["Annualised return", p(m2["Annualised return"]), p(m2["Benchmark return"]), pct(m2["Excess return"])],
            ["Volatility", p(m2["Volatility"]), p(m2["Benchmark volatility"]), pct(m2["Volatility"]-m2["Benchmark volatility"])],
            ["Sharpe ratio", f"{m2['Sharpe']:.2f}", f"{m2['Benchmark Sharpe']:.2f}", f"{m2['Sharpe']-m2['Benchmark Sharpe']:+.2f}"],
            ["Max drawdown", p(m2["Max drawdown"]), p(m2["Benchmark max drawdown"]), pct(m2["Max drawdown"]-m2["Benchmark max drawdown"])],
            ["Tracking error", p(m2["Tracking error"]), "", ""], ["Information ratio", f"{m2['Information ratio']:.2f}", "", ""],
            ["Beta to benchmark", f"{m2['Beta']:.2f}", "1.00", ""], ["Monthly hit rate", p(m2["Hit rate (months)"], 0), "", ""],
            ["Avg. holdings / active share", f"{v2.names.mean():.0f}", "", f"{p(v2.active_share.mean(), 0)}"]]
    calrows = [["Year", "Strategy", "Bench.", "Active"]] + [[str(y), p(r.Strategy), p(r.Benchmark), pct(r.Active)] for y, r in cal.iterrows()]
    side = Table([[Paragraph("Performance summary", H2), Paragraph("Calendar-year returns", H2)],
                  [tbl(perf, [W*0.23, W*0.08, W*0.09, W*0.08]), tbl(calrows, [W*0.09, W*0.12, W*0.12, W*0.12])]],
                 colWidths=[W*0.5, W*0.5])
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    S += [side, Spacer(1, 4)]
    S.append(Paragraph("Net of 10 bps per dollar traded. Benchmark = cap-weighted portfolio of the same investable universe. "
                       "Universe = current S&amp;P 500 constituents (survivorship bias affects strategy and benchmark alike; see page 2). "
                       "Hypothetical backtest, not investment advice.", SMALL))
    S.append(PageBreak())
    # ---------- Page 2 ----------
    S.append(Paragraph("How the portfolio is built", H2))
    S.append(Paragraph(
        "<b>Universe &amp; data.</b> ~340-450 US large caps per month. Prices from Yahoo Finance; fundamentals from SEC EDGAR XBRL "
        "using each value's <i>filing date</i> for point-in-time availability (no look-ahead). Share counts and prices are placed on a "
        "common split-adjusted basis; XBRL scale errors are removed with a rolling-median filter.<br/>"
        "<b>Signals.</b> Value = log book-to-market and earnings yield. Momentum = 12-month return skipping the latest month. "
        "Quality = return on equity and operating cash flow / assets. Each is winsorised at 3 sd, demeaned within GICS sector and "
        "z-scored monthly; the composite is the equal-weighted average.<br/>"
        "<b>Construction.</b> Target weight &prop; market cap &times; exp(score); sector weights rescaled to the benchmark; 5% single-name cap; "
        "<b>ex-ante beta matched to the benchmark</b> using 252-day Vasicek-shrunk betas (this is how low volatility enters: as a risk "
        "control, not a scored return factor). Monthly rebalance toward target with one-way turnover capped at 20%.", BODY))
    S.append(Paragraph("Factor attribution (Fama-French 5 + momentum, monthly active returns)", H2))
    ff = [["Factor", "Loading", "t-stat"]] + [[i.replace("Alpha (ann.)", "Alpha (annualised)"), f"{r.coef:.3f}", f"{r.t:.2f}"] for i, r in reg.iterrows()]
    S.append(Table([[tbl(ff, [W*0.2, W*0.1, W*0.1]),
                     Paragraph(f"R<super>2</super> = {r2:.2f}. Active returns load significantly on <b>momentum</b> (t = {reg.loc['MOM','t']:.1f}) "
                               f"with market, size, value and profitability loadings all statistically indistinguishable from zero, "
                               f"i.e. the beta-neutral construction removed the unintended market bet of v1. Residual alpha of "
                               f"{pct(reg.loc['Alpha (ann.)','coef'])} (t = {reg.loc['Alpha (ann.)','t']:.1f}) is not distinguishable from zero: "
                               "returns are explained by the factor exposures the strategy is designed to hold, which is the desired result "
                               "for a smart-beta product.", BODY)]],
                    colWidths=[W*0.42, W*0.58], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    S.append(Paragraph("Stress periods &amp; research history", H2))
    strows = [["Period", "Strategy", "Bench.", "Relative"]] + [[i, p(r.Strategy), p(r.Benchmark), pct(r.Relative)] for i, r in st.iterrows()]
    hist = [["", "v1: 4-factor tilt", "v2: beta-neutral"],
            ["Excess return", pct(m1["Excess return"]), pct(m2["Excess return"])],
            ["Information ratio", f"{m1['Information ratio']:.2f}", f"{m2['Information ratio']:.2f}"],
            ["90% bootstrap CI (IR)", f"[{boot1['CI5']:.2f}, {boot1['CI95']:.2f}]", f"[{boot['CI5']:.2f}, {boot['CI95']:.2f}]"],
            ["Beta", f"{m1['Beta']:.2f}", f"{m2['Beta']:.2f}"],
            ["Sharpe", f"{m1['Sharpe']:.2f}", f"{m2['Sharpe']:.2f}"],
            ["Max drawdown", p(m1["Max drawdown"]), p(m2["Max drawdown"])],
            ["IR 2011-18 / 2019-26",
             f"{split[split.version.str.startswith('v1')]['Information ratio'].iloc[0]:.2f} / {split[split.version.str.startswith('v1')]['Information ratio'].iloc[1]:.2f}",
             f"{split[split.version.str.startswith('v2')]['Information ratio'].iloc[0]:.2f} / {split[split.version.str.startswith('v2')]['Information ratio'].iloc[1]:.2f}"]]
    S.append(Table([[tbl(strows, [W*0.24, W*0.08, W*0.08, W*0.08]), tbl(hist, [W*0.2, W*0.14, W*0.14])]],
                    colWidths=[W*0.5, W*0.5], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    S.append(Spacer(1, 3))
    S.append(Paragraph(
        "<b>What v1 taught us.</b> The first version scored low volatility as a fourth return factor. It beat the benchmark on every "
        f"risk metric but lagged by {p(abs(m1['Excess return']))} a year. Regression showed the whole gap was a market-beta bet "
        f"(beta {m1['Beta']:.2f}, Mkt-RF loading t = -6.6) in a period when the market compounded at ~14% over cash, not factor failure. "
        "v2 removes the implicit short-market position and lets the return factors do the work. Both versions are reported; v2 was not "
        "selected from a grid.", BODY))
    S.append(Image(str(FIG / "v1_vs_v2_v2_betaneutral.png"), width=W*0.40, height=W*0.40*4.2/9))
    S.append(Paragraph("What this backtest cannot tell you", H2))
    S.append(Paragraph(
        f"<b>Statistical power.</b> A 15.6-year sample cannot distinguish an IR of {m2['Information ratio']:.2f} from zero "
        f"(90% block-bootstrap interval [{boot['CI5']:.2f}, {boot['CI95']:.2f}]; P(IR &gt; 0) = {boot['P_IR_pos']:.0%}). Detecting a true IR of 0.3 "
        "at conventional significance would take roughly 45 years of data. The case for the strategy rests on the long, cross-country "
        "evidence for value, momentum and quality premia and on the cleanliness of the implementation, not on this sample. "
        "<b>Survivorship.</b> The universe is today's S&amp;P 500, so both series exclude companies that failed; the benchmark's 15.7% "
        "annualised return versus ~13.7% for SPY over the same window shows the size of that bias. <b>Regime.</b> One US bull market "
        "dominated by mega-cap growth; v2's edge is concentrated in 2024-26 and driven by momentum. "
        "<b>Next steps.</b> Survivorship-free CRSP/Compustat data with history to the 1960s; intangible-adjusted value; an optimiser with an "
        "explicit tracking-error budget; and a test in international developed markets, where factor premia have been stronger.", BODY))
    S.append(Spacer(1, 4))
    S.append(Paragraph("Source: author's calculations. Code and data pipeline: github.com/[handle]/factor-strategy. Prepared September 2026. "
                       "For discussion purposes only; hypothetical performance does not reflect actual trading.", SMALL))
    doc.build(S)

if __name__ == "__main__":
    build(); print("factsheet written")
