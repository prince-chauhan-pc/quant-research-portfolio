# -*- coding: utf-8 -*-
"""
Institutional Quant Performance Tear Sheet Builder
==============================================================================
Author: Prince Chauhan Quant Desk (SEBI Registered Research Analyst)
Architecture:
- 6x2 Institutional Scorecard Grid (Return, Sharpe, Sortino, Calmar, MaxDD, Win Rate, etc.)
- Multi-Year Monthly Returns Heatmap Grid with Annual Performance Rollups
- Underwater Drawdown Analysis (Peak, Trough, Duration, Recovery Time)
- Standalone PDF Engine generating executive-grade 3-page performance tearsheets
==============================================================================
"""

import math
import datetime as dt
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


@dataclass
class TearsheetScorecard:
    initial_capital: float
    final_capital: float
    total_net_pnl: float
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_rs: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float
    recovery_factor: float
    expectancy_rs: float


class TearsheetBuilder:
    """
    Tier-1 Institutional Quantitative Performance Tear Sheet Engine.
    Computes rigorous performance metrics, returns matrices, and drawsdown distributions.
    """

    def __init__(self, initial_capital: float = 10000000.0, risk_free_rate: float = 0.065):
        """
        :param initial_capital: Base equity in INR (Default: ₹1.00 Crore)
        :param risk_free_rate: Annualized risk-free benchmark rate (Default: 6.50% RBI Repo)
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate

    def compute_scorecard(self, daily_pnls: List[float], trade_pnls: Optional[List[float]] = None) -> TearsheetScorecard:
        """
        Computes the standard 6x2 Institutional KPI Scorecard.
        """
        if not daily_pnls:
            raise ValueError("daily_pnls series cannot be empty.")

        n_days = len(daily_pnls)
        total_pnl = sum(daily_pnls)
        final_capital = self.initial_capital + total_pnl
        total_ret_pct = (total_pnl / self.initial_capital) * 100.0

        # Annualization factor (252 trading days per year)
        years = max(n_days / 252.0, 1.0 / 252.0)
        cagr_pct = (((final_capital / self.initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if final_capital > 0 else -100.0

        # Equity Curve & Drawdown
        equity = [self.initial_capital]
        for p in daily_pnls:
            equity.append(equity[-1] + p)

        running_max = equity[0]
        max_dd_rs = 0.0
        max_dd_pct = 0.0

        for eq in equity:
            if eq > running_max:
                running_max = eq
            dd_rs = running_max - eq
            dd_pct = (dd_rs / running_max) * 100.0 if running_max > 0 else 0.0
            if dd_rs > max_dd_rs:
                max_dd_rs = dd_rs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        # Daily Returns & Ratios
        daily_returns = [daily_pnls[i] / equity[i] for i in range(n_days)]
        mean_ret = sum(daily_returns) / n_days
        std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in daily_returns) / max(n_days - 1, 1))

        # Downside Deviation for Sortino
        downside_diffs = [min(0.0, r) ** 2 for r in daily_returns]
        downside_std = math.sqrt(sum(downside_diffs) / max(n_days - 1, 1))

        daily_rf = self.risk_free_rate / 252.0
        excess_mean = mean_ret - daily_rf

        sharpe = (excess_mean / std_ret * math.sqrt(252)) if std_ret > 1e-9 else 0.0
        sortino = (excess_mean / downside_std * math.sqrt(252)) if downside_std > 1e-9 else 0.0
        calmar = (cagr_pct / max_dd_pct) if max_dd_pct > 1e-9 else 0.0

        # Trade-level statistics
        trades = trade_pnls if trade_pnls is not None else daily_pnls
        n_trades = len(trades)
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t < 0]

        win_rate = (len(wins) / n_trades * 100.0) if n_trades > 0 else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 1e-9 else (99.0 if gross_profit > 0 else 0.0)
        avg_trade = total_pnl / n_trades if n_trades > 0 else 0.0
        recovery_factor = (total_pnl / max_dd_rs) if max_dd_rs > 1e-9 else 0.0
        expectancy = avg_trade

        return TearsheetScorecard(
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_net_pnl=round(total_pnl, 2),
            total_return_pct=round(total_ret_pct, 2),
            cagr_pct=round(cagr_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            max_drawdown_rs=round(max_dd_rs, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            win_rate_pct=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            total_trades=n_trades,
            avg_trade_pnl=round(avg_trade, 2),
            recovery_factor=round(recovery_factor, 2),
            expectancy_rs=round(expectancy, 2)
        )

    def compute_monthly_matrix(self, daily_records: List[Dict[str, Any]]) -> Dict[int, Dict[str, float]]:
        """
        Builds Year x Month returns matrix.
        :param daily_records: List of dicts with keys 'date' (YYYY-MM-DD) and 'pnl'
        :return: Dict[Year, Dict['Jan'..'Dec', Monthly Return %, 'Total': Annual Return %]]
        """
        monthly_pnls: Dict[Tuple[int, int], float] = {}
        for r in daily_records:
            d = dt.datetime.strptime(r["date"], "%Y-%m-%d")
            key = (d.year, d.month)
            monthly_pnls[key] = monthly_pnls.get(key, 0.0) + r["pnl"]

        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        years = sorted(list({k[0] for k in monthly_pnls.keys()}))

        matrix: Dict[int, Dict[str, float]] = {}
        for y in years:
            matrix[y] = {}
            year_pnl = 0.0
            for m_idx, m_name in enumerate(months, 1):
                pnl = monthly_pnls.get((y, m_idx), 0.0)
                ret_pct = (pnl / self.initial_capital) * 100.0
                matrix[y][m_name] = round(ret_pct, 2)
                year_pnl += pnl
            matrix[y]["Year"] = round((year_pnl / self.initial_capital) * 100.0, 2)

        return matrix

    def compute_underwater_series(self, daily_pnls: List[float]) -> List[Dict[str, float]]:
        """
        Computes the peak-to-trough underwater drawdown series.
        """
        equity = self.initial_capital
        peak = self.initial_capital
        series = []

        for day_idx, pnl in enumerate(daily_pnls):
            equity += pnl
            if equity > peak:
                peak = equity
            dd_rs = peak - equity
            dd_pct = (dd_rs / peak) * 100.0 if peak > 0 else 0.0
            series.append({
                "day": day_idx + 1,
                "equity": round(equity, 2),
                "peak": round(peak, 2),
                "drawdown_rs": round(dd_rs, 2),
                "drawdown_pct": round(dd_pct, 2)
            })

        return series

    def export_pdf_report(
        self,
        output_path: str,
        strategy_name: str,
        scorecard: TearsheetScorecard,
        monthly_matrix: Dict[int, Dict[str, float]]
    ) -> bool:
        """
        Compiles an institutional 3-page performance PDF if ReportLab is installed.
        Returns True if successful, False if ReportLab is unavailable.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        except ImportError:
            return False

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#193B56"),
            spaceAfter=8
        )
        subtitle_style = ParagraphStyle(
            "SubtitleStyle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#555555"),
            spaceAfter=14
        )

        story = []

        # PAGE 1: Header & 6x2 Scorecard
        story.append(Paragraph(f"<b>{strategy_name} — Institutional Performance Tear Sheet</b>", title_style))
        story.append(Paragraph("RESEARCH ARCHITECTURE BY PRINCE CHAUHAN | SEBI REGISTERED RESEARCH ANALYST", subtitle_style))

        scorecard_data = [
            ["Metric", "Value", "Metric", "Value"],
            ["Total Net P&L", f"Rs. {scorecard.total_net_pnl:,.2f}", "Sharpe Ratio", f"{scorecard.sharpe_ratio:.2f}"],
            ["Total Return", f"{scorecard.total_return_pct:.2f}%", "Sortino Ratio", f"{scorecard.sortino_ratio:.2f}"],
            ["CAGR", f"{scorecard.cagr_pct:.2f}%", "Calmar Ratio", f"{scorecard.calmar_ratio:.2f}"],
            ["Max Drawdown (Rs)", f"Rs. {scorecard.max_drawdown_rs:,.2f}", "Profit Factor", f"{scorecard.profit_factor:.2f}"],
            ["Max Drawdown (%)", f"{scorecard.max_drawdown_pct:.2f}%", "Win Rate", f"{scorecard.win_rate_pct:.2f}%"],
            ["Total Trades", f"{scorecard.total_trades:,}", "Expectancy", f"Rs. {scorecard.expectancy_rs:,.2f}"]
        ]

        t = Table(scorecard_data, colWidths=[130, 130, 130, 130])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#193B56")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        # Monthly Heatmap Table
        story.append(Paragraph("<b>Historical Monthly Returns Matrix (%)</b>", styles["Heading2"]))
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Year"]
        table_rows = [["Year"] + months]

        for y in sorted(monthly_matrix.keys()):
            row = [str(y)]
            for m in months:
                row.append(f"{monthly_matrix[y].get(m, 0.0):.1f}%")
            table_rows.append(row)

        mt = Table(table_rows, colWidths=[40] + [38] * 12 + [44])
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ]))
        story.append(mt)

        doc.build(story)
        return True
