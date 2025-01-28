import os
import random
import re
import time
import urllib
import shutil
from os import path

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase


class CleanStrm(_PluginBase):
    # 插件名称
    plugin_name = "定时清理无效strm"
    # 插件描述
    plugin_desc = "定时清理无效strm文件。"
    # 插件图标
    plugin_icon = "clean.png"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "su2do"
    # 作者主页
    author_url = "https://github.com/su2do"
    # 插件配置项ID前缀
    plugin_config_prefix = "cleanstrm_"
    # 加载顺序
    plugin_order = 23
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    # 任务执行间隔
    _cron = None
    _onlyonce = False
    _cleandir = False
    _cleanuser = None

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):

        # 清空配置
        self._cleanuser = {}

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._onlyonce = config.get("onlyonce")
            self._cleandir = config.get("cleandir")
            self._cleanuser = config.get("cleanuser")

        # 停止现有任务
        self.stop_service()

        if self._enabled or self._onlyonce:
            # 定时服务
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            # 运行一次定时服务
            if self._onlyonce:
                logger.info("定时清理无效strm服务启动，立即运行一次")
                self._scheduler.add_job(func=self.clean, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name="定时清理无效strm")
                # 关闭一次性开关
                self._onlyonce = False
                # 保存配置
                self.__update_config()

            # 周期运行
            if self._cron:
                try:
                    self._scheduler.add_job(func=self.clean,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name="定时清理无效strm")
                except Exception as err:
                    logger.error(f"定时任务配置错误：{err}")
                    # 推送实时消息
                    self.systemmessage.put(f"执行周期配置错误：{err}")

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def clean(self):
        suffix = None
        for cleanconfig in str(self._cleanuser).split("\n"):
            if cleanconfig.count('#') == 0:
                strm_path = cleanconfig
            elif cleanconfig.count('#') == 1:
                strm_path = cleanconfig.split('#')[0]
                suffix = cleanconfig.split('#')[1]
            elif cleanconfig.count('#') == 2:
                strm_path = cleanconfig.split("#")[0]
                replace_from = cleanconfig.split("#")[1]
                replace_to = cleanconfig.split("#")[2]
            elif cleanconfig.count('#') == 3:
                strm_path = cleanconfig.split("#")[0]
                replace_from = cleanconfig.split("#")[1]
                replace_to = cleanconfig.split("#")[2]
                suffix = cleanconfig.split("#")[3]
            else:
                logger.error(f"{cleanconfig} 格式错误")
                continue
            logger.info(f"\n======== ▷{cleanconfig} ◁ ========")
            logger.info(f"开始清除失效strm {strm_path} ")
            for root,dirs,files in os.walk(strm_path):
                for name in files:
                    if name.endswith(".strm"):
                        filename=root+"/"+name
                        f=open(filename,"r")
                        media=f.read()
                        meida_path=urllib.parse.unquote(media)
                        if suffix == None:
                            if not os.path.exists(meida_path.replace(replace_from,replace_to)):# 检查文件是否存在
                                logger.info(f"已删除 {filename} : {meida_path}")
                                os.remove(filename)  # 删除文件
                            else:
                                logger.info(f"{filename} 有效")
                        else:
                            if not os.path.exists(re.sub(r'\.[^.]*$', '.' + suffix, meida_path.replace(replace_from,replace_to))):# 检查文件是否存在
                                logger.info(f"已删除 {filename} : {meida_path}")
                                os.remove(filename)  # 删除文件
                            else:
                                logger.info(f"{filename} 有效")
            if self._cleandir:
                self.__clean_dir(strm_path)
        logger.info(f"失效strm处理完毕！")
 
    def delete_folder(self,path): 
        try:
            shutil.rmtree(path, ignore_errors=True)
        except NotADirectoryError:
            logger.error("Invalid folder path")
        except FileNotFoundError:
            logger.error("Folder not found")

    def __is_empty_dir(self,full_dir_path):
        #entries = os.listdir(full_dir_path)
        for root,dirs,files in os.walk(full_dir_path, topdown=False):
        # 检查每个条目是否为媒体文件或文件夹
            for file in files:
                full_path = os.path.join(root, file)
                if os.path.isdir(full_path):
                    # 如果目录不为空或者包含非strm文件，返回False
                    if not self.__is_empty_dir(full_path):
                        return False
                elif full_path.endswith(".strm"):# 检查文件扩展名是否为媒体文件类型
                    return False
                else:
                    logger.info(f"{full_path} 非strm文件")
            # 如果所有条目都不是媒体文件或为空，返回True
            logger.info(f"{full_dir_path} 无strm文件")
            return True

    def __clean_dir(self, directory):
        logger.info(f"开始清理文件夹 {directory} ！")
        for root,dirs,files in os.walk(directory, topdown=False):
            if not dirs:
                if  self.__is_empty_dir(root):
                    self.delete_folder(root)
                    logger.info(f"删除空目录： {root}")
                else:
                    logger.info(f"{root} 非空")
            else:
                for dir in dirs:
                    full_dir_path = os.path.join(root, dir)
                    #logger.info(f"检查 {full_dir_path}")
                    if  self.__is_empty_dir(full_dir_path):
                        self.delete_folder(full_dir_path)
                        logger.info(f"删除空目录： {full_dir_path}")
                    else:
                        logger.info(f"{full_dir_path} 非空")
        logger.info(f"清理空文件夹完成！")

    def __update_config(self):
        """
        更新配置
        """
        self.update_config({
            "onlyonce": False,
            "cron": self._cron,
            "enabled": self._enabled,
            "cleanuser": self._cleanuser,
            "cleandir": self._cleandir
        })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        if self._enabled and self._cron:
            return [
                {
                    "id": "CleanStrm",
                    "name": "清理无效strm定时服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.clean,
                    "kwargs": {}
                }
            ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }, {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'cleandir',
                                            'label': '删除空文件夹',
                                        }
                                    }
                                ]
                            }, {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            }, {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '定时任务周期',
                                            'placeholder': '30 4 * * *',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'cleanuser',
                                            'rows': 6,
                                            'label': '清理配置（若有多个，一行一个）',
                                            'placeholder': '每一行一个配置，后缀可不填若填写了后缀，则strm中的后缀部分将替换为所填后缀，若无替换词可留空\n'
                                                           'strmpath#replacefrom#replaceto#suffix\n'
                                                           '示例：检查目录#被替换词#替换词#后缀\n'
                                                           '1、/strm/电影#http://127.0.0.1:5344/d#/云盘挂载/xiaoyabox/电影\n'
                                                           '2、/strm媒体库/电影#http://127.0.0.1:5344/d#/strm生成库/电影#strm\n'
                                                           '3、/strm媒体库/电影\n',
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enable": False,
            "onlyonce": False,
            "cleandir": False,
            "cron": "30 4 * * *",
            "cleanuser": ""
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))
