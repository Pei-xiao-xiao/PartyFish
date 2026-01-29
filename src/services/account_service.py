"""
账号管理服务
负责多账号的创建、切换、删除和数据目录管理
"""

import shutil


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

    def create_account(self, account_name):
        """
        创建新账号
        :param account_name: 新账号名
        :return: True 如果创建成功，False 如果账号已存在
        """
        if not account_name or account_name.strip() == "":
            return False

        account_name = account_name.strip()
        account_dir = self.config.user_data_dir / "accounts" / account_name / "data"

        if account_dir.exists():
            return False  # 账号已存在

        account_dir.mkdir(parents=True, exist_ok=True)
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
