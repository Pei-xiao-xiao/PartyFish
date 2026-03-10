"""
账号管理服务
负责多账号的创建、切换、删除和数据目录管理
"""

import json
import shutil
from pathlib import Path


class AccountService:
    """账号管理服务类"""

    def __init__(self, config):
        """
        初始化账号服务

        Args:
            config: Config 实例引用
        """
        self.config = config

    def get_account_data_dir(self):
        """返回当前账号的数据目录"""
        return (
            self.config.user_data_dir
            / "accounts"
            / self.config.current_account
            / "data"
        )

    def get_records_file(self):
        """返回当前账号的钓鱼记录文件路径"""
        return self.get_account_data_dir() / "records.csv"

    def get_sales_file(self):
        """返回当前账号的销售记录文件路径"""
        return self.get_account_data_dir() / "sales.csv"

    def get_accounts(self):
        """获取所有账号列表"""
        accounts_dir = self.config.user_data_dir / "accounts"
        if accounts_dir.exists():
            accounts = [d.name for d in accounts_dir.iterdir() if d.is_dir()]
            if accounts:
                return sorted(accounts)
        return ["默认账号"]

    def switch_account(self, account_name):
        """
        切换账号
        :param account_name: 目标账号名
        :return: True 如果切换成功
        """
        self.config.current_account = account_name
        # 确保账号数据目录存在
        account_dir = self.get_account_data_dir()
        account_dir.mkdir(parents=True, exist_ok=True)
        self.config.save()
        return True

    def delete_account(self, account_name):
        """
        删除账号
        :param account_name: 要删除的账号名
        :return: True 如果删除成功
        """
        if account_name == self.config.current_account:
            return False  # 不能删除当前正在使用的账号

        account_dir = self.config.user_data_dir / "accounts" / account_name
        if account_dir.exists():
            shutil.rmtree(account_dir)
            return True
        return False

    def get_account_settings_file(self, account_name=None):
        """
        返回账号设置文件路径
        :param account_name: 账号名，默认为当前账号
        """
        if account_name is None:
            account_name = self.config.current_account
        return (
            self.config.user_data_dir
            / "accounts"
            / account_name
            / "account_settings.json"
        )

    def get_account_settings(self, account_name=None):
        """
        获取账号设置
        :param account_name: 账号名，默认为当前账号
        :return: 账号设置字典
        """
        settings_file = self.get_account_settings_file(account_name)
        default_settings = {"server_region": "CN"}

        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    default_settings.update(settings)
            except (json.JSONDecodeError, Exception):
                pass

        return default_settings

    def save_account_settings(self, settings, account_name=None):
        """
        保存账号设置
        :param settings: 设置字典
        :param account_name: 账号名，默认为当前账号
        """
        settings_file = self.get_account_settings_file(account_name)
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

    def get_account_server_region(self, account_name=None):
        """
        获取账号的区服设置
        :param account_name: 账号名，默认为当前账号
        :return: "CN" 或 "Global"
        """
        settings = self.get_account_settings(account_name)
        return settings.get("server_region", "CN")

    def set_account_server_region(self, region, account_name=None):
        """
        设置账号的区服
        :param region: "CN" 或 "Global"
        :param account_name: 账号名，默认为当前账号
        """
        settings = self.get_account_settings(account_name)
        settings["server_region"] = region
        self.save_account_settings(settings, account_name)

    def create_account(self, account_name, server_region="CN"):
        """
        创建新账号
        :param account_name: 新账号名
        :param server_region: 区服设置，"CN" 或 "Global"
        :return: True 如果创建成功，False 如果账号已存在
        """
        if not account_name or account_name.strip() == "":
            return False

        account_name = account_name.strip()
        account_dir = self.config.user_data_dir / "accounts" / account_name / "data"

        if account_dir.exists():
            return False  # 账号已存在

        account_dir.mkdir(parents=True, exist_ok=True)

        self.set_account_server_region(server_region, account_name)

        return True
