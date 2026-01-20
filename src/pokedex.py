"""
图鉴数据管理模块
负责管理鱼类数据和用户收集状态
"""
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.config import cfg

# 品质列表（与 components.py 保持一致）
QUALITIES = ["标准", "非凡", "稀有", "史诗", "传奇"]


from PySide6.QtCore import QObject, Signal

class Pokedex(QObject):
    """
    图鉴数据管理类
    - 加载 fish.json 鱼类数据
    - 管理用户收集状态 pokedex.json
    - 同步 records.csv 更新收集状态
    """
    
    # 添加数据变更信号
    data_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self._fish_data: List[Dict] = []
        self._collection: Dict[str, Dict[str, Optional[float]]] = {}
        self._load_fish_data()
        self._load_collection()
    
    def _get_pokedex_path(self) -> Path:
        """获取当前账号的图鉴数据路径"""
        return cfg.user_data_dir / "accounts" / cfg.current_account / "pokedex.json"
    
    def _load_fish_data(self):
        """加载 fish.json 鱼类数据"""
        fish_path = cfg._get_base_path() / "resources" / "fish.json"
        if fish_path.exists():
            try:
                with open(fish_path, 'r', encoding='utf-8') as f:
                    self._fish_data = json.load(f)
            except Exception as e:
                print(f"[Pokedex] 加载 fish.json 失败: {e}")
                self._fish_data = []
    
    def _load_collection(self):
        """加载用户收集数据"""
        path = self._get_pokedex_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self._collection = json.load(f)
            except Exception as e:
                print(f"[Pokedex] 加载图鉴数据失败: {e}")
                self._collection = {}
        else:
            self._collection = {}
    
    def _save_collection(self):
        """保存用户收集数据"""
        path = self._get_pokedex_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._collection, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Pokedex] 保存图鉴数据失败: {e}")
    
    def reload(self):
        """重新加载数据（账号切换时调用）"""
        # self._load_fish_data() # 鱼类数据是静态的，不需要重新加载
        self._load_collection()
        self.data_changed.emit()
    
    def get_all_fish(self) -> List[Dict]:
        """获取所有可显示的鱼类数据（过滤 show_in_pokedex=false）"""
        return [f for f in self._fish_data if f.get('show_in_pokedex', True)]
    
    def get_fish_types(self) -> List[str]:
        """获取所有钓竿类型"""
        types = set()
        for fish in self._fish_data:
            if 'type' in fish:
                types.add(fish['type'])
        return sorted(types)
    
    def get_fish_by_type(self, fish_type: str) -> List[Dict]:
        """按钓竿类型筛选鱼类"""
        visible_fish = [f for f in self._fish_data if f.get('show_in_pokedex', True)]
        if not fish_type or fish_type == "全部":
            return visible_fish
        return [f for f in visible_fish if f.get('type') == fish_type]
    
    def search_fish(self, keyword: str) -> List[Dict]:
        """搜索鱼类（按名称）"""
        visible_fish = [f for f in self._fish_data if f.get('show_in_pokedex', True)]
        if not keyword:
            return visible_fish
        keyword = keyword.lower()
        return [f for f in visible_fish if keyword in f.get('name', '').lower()]
    
    def get_fish_image_path(self, fish_name: str) -> Optional[Path]:
        """获取鱼类图片路径"""
        base_path = cfg._get_base_path() / "resources" / "fish"
        # 尝试多种可能的文件名
        for ext in ['.png', '.jpg', '.jpeg']:
            path = base_path / f"{fish_name}{ext}"
            if path.exists():
                return path
        return None
    
    def get_collection_status(self, fish_name: str) -> Dict[str, Optional[float]]:
        """
        获取指定鱼类的收集状态
        返回: {品质: 最大重量 或 None}
        """
        if fish_name not in self._collection:
            return {q: None for q in QUALITIES}
        
        status = self._collection[fish_name]
        # 确保所有品质都有值
        return {q: status.get(q) for q in QUALITIES}
    
    def is_collected(self, fish_name: str, quality: str) -> bool:
        """检查某品质是否已收集"""
        return self._collection.get(fish_name, {}).get(quality) is not None
    
    def mark_caught(self, fish_name: str, quality: str, weight: Optional[float] = 0):
        """
        标记某品质已收集
        :param fish_name: 鱼名
        :param quality: 品质
        :param weight: 重量（手动标记时为 0）
        """
        if fish_name not in self._collection:
            self._collection[fish_name] = {}
        
        current = self._collection[fish_name].get(quality)
        # 如果已有记录且新重量更大，更新重量
        if current is None or (weight is not None and weight > current):
            self._collection[fish_name][quality] = weight
        
        self._save_collection()
        self.data_changed.emit()
    
    def mark_uncaught(self, fish_name: str, quality: str):
        """取消某品质的收集标记"""
        if fish_name in self._collection and quality in self._collection[fish_name]:
            self._collection[fish_name][quality] = None
            self._save_collection()
            self.data_changed.emit()
    
    def mark_all_caught(self, fish_name: str):
        """标记所有品质为已收集（重量设为 0）"""
        self._collection[fish_name] = {q: 0 for q in QUALITIES}
        self._save_collection()
        self.data_changed.emit()
    
    def clear_all(self, fish_name: str):
        """清空某鱼的所有收集状态"""
        if fish_name in self._collection:
            self._collection[fish_name] = {}
            self._save_collection()
            self.data_changed.emit()
    
    def toggle_quality(self, fish_name: str, quality: str):
        """切换某品质的收集状态"""
        if self.is_collected(fish_name, quality):
            self.mark_uncaught(fish_name, quality)
        else:
            self.mark_caught(fish_name, quality, 0)
    
    def sync_from_records(self) -> int:
        """
        从 records.csv 同步收集数据
        返回: 新增收集数量
        """
        records_path = cfg.records_file
        if not records_path.exists():
            return 0
        
        new_count = 0
        try:
            with open(records_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Name', '').strip()
                    quality = row.get('Quality', '').strip()
                    weight_str = row.get('Weight', '0')
                    
                    if not name or not quality:
                        continue
                    
                    # 解析重量
                    try:
                        weight = float(weight_str.replace('g', '').strip())
                    except ValueError:
                        weight = 0
                    
                    # 检查是否为新收集
                    if not self.is_collected(name, quality):
                        new_count += 1
                    
                    # 更新收集状态（会自动保留最大重量）
                    self.mark_caught(name, quality, weight)
        
        except Exception as e:
            print(f"[Pokedex] 同步 records.csv 失败: {e}")
        
        if new_count > 0:
            self.data_changed.emit()
            
        return new_count
    
    def get_progress(self) -> tuple:
        """
        获取收集进度（仅计算可显示的鱼类）
        返回: (已收集鱼类数, 总鱼类数, 已收集总品质数, 总可收集品质数)
        """
        visible_fish = [f for f in self._fish_data if f.get('show_in_pokedex', True)]
        total_fish = len(visible_fish)
        collected_fish = 0
        
        total_qualities = total_fish * len(QUALITIES)
        collected_qualities_total = 0
        
        for fish in visible_fish:
            name = fish.get('name', '')
            status = self.get_collection_status(name)
            # 该鱼已收集的品质数
            q_count = sum(1 for v in status.values() if v is not None)
            
            if q_count > 0:
                collected_fish += 1
            
            collected_qualities_total += q_count
        
        return collected_fish, total_fish, collected_qualities_total, total_qualities
    
    def get_fish_collected_count(self, fish_name: str) -> int:
        """获取某鱼已收集的品质数量"""
        status = self.get_collection_status(fish_name)
        return sum(1 for v in status.values() if v is not None)

    @staticmethod
    def get_current_game_time() -> str:
        """
        获取当前游戏时段
        对应关系 (每小时分钟数):
        00-10: 凌晨
        10-20: 清晨
        20-30: 上午
        30-40: 下午
        40-50: 黄昏
        50-00: 深夜
        """
        minute = datetime.now().minute
        if 0 <= minute < 10:
            return "凌晨"
        elif 10 <= minute < 20:
            return "清晨"
        elif 20 <= minute < 30:
            return "上午"
        elif 30 <= minute < 40:
            return "下午"
        elif 40 <= minute < 50:
            return "黄昏"
        else:
            return "深夜"

    def get_filter_options(self) -> Dict[str, List[str]]:
        """获取所有筛选选项的动态列表"""
        options = {
            "weather": set(),
            "location": set(),
            "season": set()
        }
        
        for fish in self._fish_data:
            if not fish.get('show_in_pokedex', True):
                continue
                
            for loc in fish.get('locations', []):
                # 收集地点
                if loc.get('location'):
                    options["location"].add(loc['location'])
                
                for cond in loc.get('conditions', []):
                    # 收集天气
                    for w in cond.get('weather', []):
                        options["weather"].add(w)
                    # 收集季节
                    for s in cond.get('season', []):
                        options["season"].add(s)
        
        # 排序并转为列表
        # 自定义排序逻辑（可选），这里直接字典序或保持常见顺序
        # 季节排序
        season_order = ["春季", "夏季", "秋季", "冬季"]
        sorted_season = sorted(list(options["season"]), key=lambda x: season_order.index(x) if x in season_order else 99)
        
        return {
            "weather": sorted(list(options["weather"])),
            "location": sorted(list(options["location"])),
            "season": sorted_season
        }

    def filter_fish_multi(self, fish_list: List[Dict], criteria: Dict[str, List[str]]) -> List[Dict]:
        """
        多条件组合筛选
        criteria 结构: {
            "time": ["凌晨", "清晨"...],
            "weather": ["晴天", ...],
            "location": ["岸边", ...],
            "type": ["路亚轻竿"],
            "season": ["春季"],
            "collection": ["collected", "uncollected", "all_collected"]
        }
        逻辑:
        1. 类别内为 OR (如选中 晴天 或 多云 -> 显示任意一种)
        2. 类别间为 AND (如 晴天 且 岸边 -> 必须同时满足)
        """
        if not criteria:
            return fish_list
            
        result = []
        for fish in fish_list:
            is_match = True
            
            # 1. 筛选基本属性 (Type)
            if criteria.get("type"):
                if fish.get("type") not in criteria["type"]:
                    is_match = False
            
            if not is_match: continue
            
            # 2. 筛选复杂条件 (Location, Time, Weather, Season)
            # 只要有一个 location 满足所有选中的条件类别即可 (OR 逻辑在 location 内部通常是 AND 关系，
            # 但这里我们要看用户选了什么。
            # 如果用户选了 "晴天", "雨天" -> this fish supports (Sunny OR Rainy)? Yes.
            # 如果用户选了 "晴天" AND "岸边" -> this fish supports (Sunny AND 岸边)? Yes.
            
            # 预处理 location条件
            target_locs = set(criteria.get("location", []))
            target_times = set(criteria.get("time", []))
            target_weathers = set(criteria.get("weather", []))
            target_seasons = set(criteria.get("season", []))
            
            # 检查是否有任意一个 location 块满足所有"非空"的筛选维度
            # 注意：如果一个维度用户没选，就视为满足该维度
            
            location_match_found = False
            
            # 如果没有涉及 Location 内的属性筛选，直接跳过此步检查
            if not any([target_locs, target_times, target_weathers, target_seasons]):
                location_match_found = True
            else:
                for loc in fish.get('locations', []):
                    # 2.1 地点检查
                    if target_locs and loc.get('location') not in target_locs:
                        continue
                        
                    # 检查 conditions
                    # 一个 location 可能有多个 condition (不同季节/时间段可能不同)
                    # 只要有一个 condition 满足 Time/Weather/Season 即可
                    condition_match_found = False
                    for cond in loc.get('conditions', []):
                        # 2.2 时间检查 (OR: 鱼的时间列表与筛选时间列表有交集)
                        if target_times:
                            fish_times = set(cond.get('time_of_day', []))
                            if not fish_times.intersection(target_times):
                                continue # 该 condition 不满足时间
                        
                        # 2.3 天气检查 (OR)
                        if target_weathers:
                            fish_weathers = set(cond.get('weather', []))
                            if not fish_weathers.intersection(target_weathers):
                                continue
                        
                        # 2.4 季节检查 (OR)
                        if target_seasons:
                            fish_seasons = set(cond.get('season', []))
                            if not fish_seasons.intersection(target_seasons):
                                continue
                        
                        # 如果都通过
                        condition_match_found = True
                        break
                    
                    if condition_match_found:
                        location_match_found = True
                        break
            
            if not location_match_found:
                is_match = False
            
            if not is_match: continue
            
            # 3. 收集状态筛选
            coll_criteria = criteria.get("collection", [])
            if coll_criteria:
                status = self.get_collection_status(fish.get("name"))
                collected_count = sum(1 for v in status.values() if v is not None)
                is_full = collected_count == len(QUALITIES)
                is_any = collected_count > 0
                
                # 逻辑：
                # "uncaught": 未解锁 (collected_count == 0) (注：用户原话是 "只显示未全部解锁" 或 "只显示未解锁")
                # 参考图片：
                # "只显示未全部解锁": collected_count < 5
                # "只显示未解锁": collected_count = 0 ??? 或者是 "未收集的条目"
                # 通常理解：
                # "uncollected": 完全没钓到过
                # "incomplete": 钓到过但没齐
                # "completed": 全齐
                
                # 假设前端传递的标记：
                # 'hide_completed': 隐藏已全收集的 -> means show (not fully collected)
                # 'show_uncaught_only': 只看未开图鉴的 -> means show (collected == 0)
                
                # 简化处理：让前端传入允许的状态
                # 'completed': 包含全收集
                # 'incomplete': 包含未全收集 (0 < count < 5)
                # 'uncaught': 包含未收集 (count == 0)
                
                # 但根据图示，用户有特定按钮。
                # 按钮1: "只显示未全部解锁" -> 排除 All Collected
                if "hide_completed" in coll_criteria and is_full:
                    is_match = False
                # 按钮2: "只显示未解锁" -> 只保留 count == 0
                if "only_uncaught" in coll_criteria and is_any:
                    is_match = False
            
            if is_match:
                result.append(fish)
                
        return result

    def filter_by_time(self, fish_list: List[Dict], time_period: str) -> List[Dict]:
        """
        兼容保留：筛选在该时段出没的鱼类
        """
        if not time_period:
            return fish_list
        return self.filter_fish_multi(fish_list, {"time": [time_period]})

    def sort_fish(self, fish_list: List[Dict], sort_key: str, reverse: bool = False) -> List[Dict]:
        """
        对鱼类列表进行排序
        :param fish_list: 待排序列表
        :param sort_key: 排序键 ('default', 'name', 'progress', 'weight')
        :param reverse: 是否倒序
        """
        if sort_key == 'name':
            # 按名称排序 (中文名称)
            return sorted(fish_list, key=lambda x: x.get('name', ''), reverse=reverse)
            
        elif sort_key == 'progress':
            # 按"未收集权重"排序
            # 权重规则：传奇(16) > 史诗(8) > 稀有(4) > 非凡(2) > 标准(1)
            # 得分越高 = 缺的品质越高级/越多 = 优先级越高 = 应该排在前面
            # 默认排序(reverse=False)应该显示: 优先级高 -> 优先级低 (即 Score 大 -> 小)
            
            weight_map = {
                "传奇": 16,
                "史诗": 8,
                "稀有": 4,
                "非凡": 2,
                "标准": 1
            }
            
            def get_uncollected_score(fish):
                name = fish.get('name', '')
                status = self.get_collection_status(name)
                score = 0
                for q, w in weight_map.items():
                    # 如果该品质未收集 (value is None)，则加上对应权重
                    if status.get(q) is None:
                        score += w
                return score
            
            # 默认(reverse=False)时期望: 未收集(分高) -> 已收集(分低)
            # sorted 默认是 小->大。
            # 为了让 分高 排前面，直接用 -score
            return sorted(fish_list, key=lambda f: -get_uncollected_score(f), reverse=reverse)
            
        elif sort_key == 'weight':
            # 按最大重量排序
            def get_max_weight(fish):
                status = self.get_collection_status(fish.get('name', ''))
                weights = [w for w in status.values() if w is not None]
                return max(weights) if weights else 0
            return sorted(fish_list, key=get_max_weight, reverse=reverse)
            
        else:
            # 默认排序 (列表原序)
            if reverse:
                return list(reversed(fish_list))
            return fish_list


# 全局单例
pokedex = Pokedex()
