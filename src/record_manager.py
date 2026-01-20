import csv
from pathlib import Path
from datetime import datetime
from src.config import cfg

class RecordManager:
    """记录管理模块，负责导入导出钓鱼记录"""
    
    @staticmethod
    def export_records(file_path: Path, format_type: str) -> bool:
        """
        导出记录到指定文件
        
        Args:
            file_path: 导出文件路径
            format_type: 导出格式，可选 'csv' 或 'txt'
            
        Returns:
            bool: 导出是否成功
        """
        try:
            records_file = cfg.records_file
            if not records_file.exists():
                return False
            
            # 读取所有记录
            records = []
            with open(records_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
            
            if format_type == 'csv':
                # 直接导出为CSV格式
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    fieldnames = ['Timestamp', 'Name', 'Quality', 'Weight', 'IsNewRecord', 'Bait', 'BaitCost']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for record in records:
                        writer.writerow(record)
            
            elif format_type == 'txt':
                # 导出为 |时间|鱼名|品质|重量 格式
                with open(file_path, 'w', encoding='utf-8') as f:
                    for record in records:
                        # 格式化记录
                        formatted = f"|{record['Timestamp']}|{record['Name']}|{record['Quality']}|{record['Weight']}|"
                        f.write(formatted + '\n')
            
            return True
        except Exception as e:
            print(f"导出记录失败: {e}")
            return False
    
    @staticmethod
    def import_records(file_path: Path) -> tuple[bool, str]:
        """
        从指定文件导入记录
        
        Args:
            file_path: 导入文件路径
            
        Returns:
            tuple[bool, str]: (导入是否成功, 错误信息或成功信息)
        """
        try:
            records_file = cfg.records_file
            file_extension = file_path.suffix.lower()
            
            records_to_import = []
            
            if file_extension == '.csv':
                # 从CSV文件导入
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 验证必要字段
                        if all(field in row for field in ['Timestamp', 'Name', 'Quality', 'Weight']):
                            records_to_import.append(row)
                        else:
                            return False, f"CSV文件格式不正确，缺少必要字段: {row}"
            
            elif file_extension == '.txt':
                # 从TXT文件导入，格式为 |时间|鱼名|品质|重量|
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 解析TXT格式记录
                        record = RecordManager._parse_txt_record(line)
                        if record:
                            records_to_import.append(record)
                        else:
                            return False, f"TXT文件格式不正确，第{line_num}行: {line}"
            
            else:
                return False, f"不支持的文件格式: {file_extension}"
            
            if not records_to_import:
                return False, "没有找到可导入的记录"
            
            # 追加到现有记录文件
            file_exists = records_file.exists()
            with open(records_file, 'a', encoding='utf-8', newline='') as f:
                fieldnames = ['Timestamp', 'Name', 'Quality', 'Weight', 'IsNewRecord', 'Bait', 'BaitCost']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # 如果文件不存在，写入表头
                if not file_exists:
                    writer.writeheader()
                
                # 写入导入的记录
                for record in records_to_import:
                    # 确保所有字段都存在
                    writer.writerow({
                        'Timestamp': record.get('Timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        'Name': record.get('Name', ''),
                        'Quality': record.get('Quality', ''),
                        'Weight': record.get('Weight', ''),
                        'IsNewRecord': record.get('IsNewRecord', 'No'),
                        'Bait': record.get('Bait', '蔓越莓'),
                        'BaitCost': record.get('BaitCost', '1')
                    })
            
            return True, f"成功导入 {len(records_to_import)} 条记录"
        except Exception as e:
            return False, f"导入记录失败: {str(e)}"
    
    @staticmethod
    def _parse_txt_record(line: str) -> dict or None:
        """
        解析TXT格式的记录行
        支持格式: |时间|鱼名|品质|重量|
        
        Args:
            line: 记录行
            
        Returns:
            dict or None: 解析后的记录字典，解析失败返回None
        """
        try:
            # 处理可能的空格
            line = line.strip()
            
            # 检查是否是我们导出的格式
            if line.startswith('|') and line.endswith('|'):
                # 移除首尾的 | 字符
                content = line[1:-1]
                # 分割字段
                parts = content.split('|')
                if len(parts) != 4:
                    return None
                
                # 提取字段
                timestamp, name, quality, weight = parts
            else:
                # 尝试处理其他格式（如 | 分隔但没有首尾 |）
                parts = line.split('|')
                if len(parts) < 3:
                    return None
                
                # 根据字段数量处理
                if len(parts) == 5:
                    # 格式：文件名|时间|名称|品质|重量
                    # 例如：20251222_043604|2025-12-22 04:36:40|黄鸭叫|史诗|15.54kg
                    timestamp, name, quality, weight = parts[1], parts[2], parts[3], parts[4]
                elif len(parts) == 4:
                    # 可能的格式：文件名|时间|名称|重量
                    # 或者：时间|名称|品质|重量
                    # 尝试解析时间字段
                    try:
                        # 尝试将第二个字段解析为时间
                        datetime.strptime(parts[1], "%Y-%m-%d %H:%M:%S")
                        timestamp, name, quality, weight = parts[1], parts[2], parts[0], parts[3]
                    except ValueError:
                        # 尝试将第一个字段解析为时间
                        try:
                            datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                            timestamp, name, quality, weight = parts
                        except ValueError:
                            return None
                elif len(parts) == 3:
                    # 格式：时间|名称|重量
                    # 品质默认为"标准"
                    try:
                        datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                        timestamp, name, weight = parts
                        quality = "标准"
                    except ValueError:
                        return None
                else:
                    return None
            
            # 清理字段
            timestamp = timestamp.strip()
            name = name.strip()
            quality = quality.strip()
            weight = weight.strip()
            
            # 验证时间格式
            # 处理可能的时间格式问题，如缺少空格
            if ' ' not in timestamp:
                # 尝试修复时间格式，如 2025-12-2204:36:40 -> 2025-12-22 04:36:40
                import re
                fixed_timestamp = re.sub(r'(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})', r'\1 \2', timestamp)
                datetime.strptime(fixed_timestamp, "%Y-%m-%d %H:%M:%S")
                timestamp = fixed_timestamp
            else:
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            
            # 清理重量单位
            if weight.endswith('kg'):
                weight = weight[:-2].strip()
            
            return {
                'Timestamp': timestamp,
                'Name': name,
                'Quality': quality,
                'Weight': weight,
                'IsNewRecord': 'No',
                'Bait': '蔓越莓',
                'BaitCost': '1'
            }
        except Exception as e:
            print(f"解析记录失败: {line}, 错误: {e}")
            return None

# 实例化单例
record_manager = RecordManager()