"""
PDF Generator - 生成 WSJ 风格的 TOEIC 学习 PDF
基于原有 generate_warsh_pdf.py 优化
"""
import json
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

from .config import CHINESE_FONT_PATH, ARIAL_UNICODE_PATH, OUTPUT_DIR
from .translator import TranslatedArticle


def _register_fonts():
    """注册字体"""
    try:
        pdfmetrics.registerFont(TTFont('Songti', CHINESE_FONT_PATH, subfontIndex=0))
        pdfmetrics.registerFont(TTFont('ArialUnicode', ARIAL_UNICODE_PATH))
        return True
    except Exception as e:
        print(f"[PDF] Error loading fonts: {e}")
        return False


def _get_styles():
    """获取所有样式定义"""
    styles = getSampleStyleSheet()
    
    return {
        'header': ParagraphStyle(
            'Header', 
            fontName='Times-Bold', 
            fontSize=14, 
            alignment=1, 
            spaceAfter=6
        ),
        'subheader': ParagraphStyle(
            'SubHeader', 
            fontName='Songti', 
            fontSize=10, 
            alignment=1, 
            spaceAfter=20, 
            textColor=colors.gray
        ),
        'title': ParagraphStyle(
            'WSJ_Title',
            parent=styles['Heading1'],
            fontName='Times-Bold',
            fontSize=20,
            leading=24,
            spaceAfter=8,
            textColor=colors.black,
            alignment=1
        ),
        'title_cn': ParagraphStyle(
            'WSJ_Title_Cn',
            parent=styles['Heading1'],
            fontName='Songti',
            fontSize=14,
            leading=18,
            spaceAfter=14,
            textColor=colors.black,
            alignment=1
        ),
        'subhead': ParagraphStyle(
            'WSJ_Subhead',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=11,
            leading=13,
            spaceAfter=4,
            textColor=colors.gray,
            alignment=1
        ),
        'subhead_cn': ParagraphStyle(
            'WSJ_Subhead_Cn',
            parent=styles['Normal'],
            fontName='Songti',
            fontSize=10,
            leading=12,
            spaceAfter=10,
            textColor=colors.gray,
            alignment=1
        ),
        'byline': ParagraphStyle(
            'WSJ_Byline',
            parent=styles['Normal'],
            fontName='Times-Bold',
            fontSize=9,
            leading=11,
            spaceAfter=14,
            textColor=colors.black,
            alignment=1
        ),
        'body_en': ParagraphStyle(
            'Body_En',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=9,
            leading=12,
            alignment=4,
            spaceBefore=3,
            spaceAfter=3
        ),
        'body_cn': ParagraphStyle(
            'Body_Cn',
            parent=styles['Normal'],
            fontName='Songti',
            fontSize=9,
            leading=12,
            alignment=4,
            spaceBefore=3,
            spaceAfter=3
        ),
        'vocab_header': ParagraphStyle(
            'Vocab_Header',
            parent=styles['Heading1'],
            fontName='Times-Bold',
            fontSize=16,
            leading=20,
            spaceAfter=4,
            spaceBefore=16,
            textColor=colors.HexColor('#333333'),
            alignment=1
        ),
        'vocab_header_cn': ParagraphStyle(
            'Vocab_Header_Cn',
            parent=styles['Heading1'],
            fontName='Songti',
            fontSize=14,
            leading=18,
            spaceAfter=12,
            textColor=colors.HexColor('#333333'),
            alignment=1
        ),
        'vocab_word': ParagraphStyle(
            'Vocab_Word',
            parent=styles['Normal'],
            fontName='Times-Bold',
            fontSize=11,
            leading=13,
            textColor=colors.HexColor('#1a5276'),
            spaceBefore=6,
            spaceAfter=2
        ),
        'vocab_phonetic': ParagraphStyle(
            'Vocab_Phonetic',
            parent=styles['Normal'],
            fontName='ArialUnicode',
            fontSize=9,
            leading=11,
            textColor=colors.gray,
            spaceAfter=3
        ),
        'vocab_meaning': ParagraphStyle(
            'Vocab_Meaning',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=9,
            leading=11,
            spaceAfter=2
        ),
        'vocab_meaning_cn': ParagraphStyle(
            'Vocab_Meaning_Cn',
            parent=styles['Normal'],
            fontName='Songti',
            fontSize=9,
            leading=11,
            spaceAfter=3
        ),
        'vocab_example': ParagraphStyle(
            'Vocab_Example',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#555555'),
            leftIndent=8,
            spaceAfter=2
        ),
        'vocab_example_cn': ParagraphStyle(
            'Vocab_Example_Cn',
            parent=styles['Normal'],
            fontName='Songti',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#555555'),
            leftIndent=8,
            spaceAfter=6
        ),
    }


def _get_output_dir(date: str, subdir: str) -> Path:
    """获取按日期分类的输出目录
    
    Args:
        date: 日期字符串 (如 2026-02-01)
        subdir: 子目录名 ('pdf' 或 'json')
    
    Returns:
        output/{date}/{subdir}/ 路径
    """
    target_dir = OUTPUT_DIR / date / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def generate_pdf(article: TranslatedArticle, output_path: Path = None) -> Path:
    """
    生成 PDF 文件
    
    Args:
        article: 翻译后的文章
        output_path: 输出路径，默认使用 OUTPUT_DIR/{date}/pdf/
    
    Returns:
        生成的 PDF 文件路径
    """
    _register_fonts()
    styles = _get_styles()
    
    # 生成文件名 (不再包含日期前缀，因为已经在目录中)
    safe_title = "".join(c for c in article.title[:50] if c.isalnum() or c in ' -_').strip()
    safe_title = safe_title.replace(' ', '_')
    filename = f"{safe_title}.pdf"
    
    if output_path is None:
        pdf_dir = _get_output_dir(article.date, "pdf")
        output_path = pdf_dir / filename
    
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )
    
    story = []
    
    # Header
    story.append(Paragraph("THE WALL STREET JOURNAL.", styles['header']))
    story.append(Paragraph("TOEIC Reading Practice | 托业阅读练习", styles['subheader']))
    
    # Title
    story.append(Paragraph(article.title, styles['title']))
    story.append(Paragraph(article.title_cn, styles['title_cn']))
    
    # Subhead
    if article.subhead:
        story.append(Paragraph(article.subhead, styles['subhead']))
        story.append(Paragraph(article.subhead_cn, styles['subhead_cn']))
    
    # Byline
    if article.byline:
        story.append(Paragraph(article.byline.upper(), styles['byline']))
    
    story.append(Spacer(1, 8))
    
    # Two-column body
    col_width = (A4[0] - 70) / 2 - 8
    table_data = []
    
    for p in article.paragraphs:
        p_en = Paragraph(p['en'], styles['body_en'])
        p_cn = Paragraph(p['cn'], styles['body_cn'])
        table_data.append([p_en, p_cn])
    
    t = Table(table_data, colWidths=[col_width, col_width])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEAFTER', (0, 0), (0, -1), 0.5, colors.lightgrey),
    ]))
    
    story.append(t)
    
    # Vocabulary section
    if article.vocabulary:
        story.append(PageBreak())
        story.append(Paragraph("TOEIC Vocabulary Study", styles['vocab_header']))
        story.append(Paragraph("托业词汇学习", styles['vocab_header_cn']))
        story.append(Spacer(1, 8))
        
        for i, vocab in enumerate(article.vocabulary, 1):
            story.append(Paragraph(f"<b>{i}. {vocab.get('word', '')}</b>", styles['vocab_word']))
            story.append(Paragraph(vocab.get('phonetic', ''), styles['vocab_phonetic']))
            story.append(Paragraph(f"EN: {vocab.get('meaning_en', '')}", styles['vocab_meaning']))
            story.append(Paragraph(vocab.get('meaning_cn', ''), styles['vocab_meaning_cn']))
            story.append(Paragraph(f'"{vocab.get("example", "")}"', styles['vocab_example']))
            story.append(Paragraph(f'"{vocab.get("example_cn", "")}"', styles['vocab_example_cn']))
            
            if i % 5 == 0 and i < len(article.vocabulary):
                story.append(Spacer(1, 6))
    
    # Build PDF
    doc.build(story)
    print(f"[PDF] Generated: {output_path}")
    
    return output_path


def save_json(article: TranslatedArticle, output_path: Path = None) -> Path:
    """保存 JSON 格式数据"""
    safe_title = "".join(c for c in article.title[:50] if c.isalnum() or c in ' -_').strip()
    safe_title = safe_title.replace(' ', '_')
    filename = f"{safe_title}.json"
    
    if output_path is None:
        json_dir = _get_output_dir(article.date, "json")
        output_path = json_dir / filename
    
    data = {
        "title": article.title,
        "title_cn": article.title_cn,
        "subhead": article.subhead,
        "subhead_cn": article.subhead_cn,
        "byline": article.byline,
        "byline_cn": article.byline_cn,
        "paragraphs": article.paragraphs,
        "vocabulary": article.vocabulary,
        "original_url": article.original_url,
        "date": article.date,
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"[JSON] Saved: {output_path}")
    return output_path
