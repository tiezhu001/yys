# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from time import sleep, monotonic
from datetime import time, datetime, timedelta

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from tasks.Orochi.assets import OrochiAssets
from tasks.Orochi.page import page_orochi
from tasks.Orochi.config import Orochi, UserStatus, Layer
from tasks.TrueOrochi.assets import TrueOrochiAssets
from module.atom.ocr import RuleOcr
from module.logger import logger
from module.exception import TaskEnd, GameStuckError


class ScriptTask(GeneralBattle, GeneralInvite, GeneralBuff, GeneralRoom, GameUi, SwitchSoul, OrochiAssets, TrueOrochiAssets):

    def run(self) -> bool:
        # 御魂切换方式一
        if self.config.orochi.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(self.config.orochi.switch_soul.switch_group_team)

        # 御魂切换方式二
        if self.config.orochi.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.orochi.switch_soul.group_name,
                                         self.config.orochi.switch_soul.team_name)
        # 根据选层切换御魂
        self.orochi_switch_soul()

        limit_count = self.config.orochi.orochi_config.limit_count
        limit_time = self.config.orochi.orochi_config.limit_time
        # 调度器重试时复用同一个御魂周期，避免中途错误后次数和限时被清零。
        cycle_state = getattr(self.config, '_orochi_cycle_state', None)
        if cycle_state is None:
            cycle_state = {
                'count': 0,
                'start_time': datetime.now(),
            }
            self.config._orochi_cycle_state = cycle_state
        self.current_count = cycle_state['count']
        self.start_time = cycle_state['start_time']
        self.limit_count: int = limit_count
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)

        config: Orochi = self.config.orochi
        if not self.is_in_battle(True):
            if config.orochi_config.soul_buff_enable:
                self.goto_page(page_main)
                self.open_buff()
                self.soul(is_open=True)
                self.close_buff()

        success = True
        match config.orochi_config.user_status:
            case UserStatus.LEADER: success = self.run_leader()
            case UserStatus.MEMBER: success = self.run_member()
            case UserStatus.ALONE: self.run_alone()
            case UserStatus.WILD: success = self.run_wild()
            case _: logger.error('Unknown user status')

        # 御魂结束后检测是否出现真蛇
        if config.orochi_config.check_true_orochi_enable:
            self.goto_page(page_orochi)
            self.screenshot()
            if self.appear(self.I_FIND_TS):
                logger.info('Find true orochi after orochi battle, set TrueOrochi task to run now')
                self.set_next_run(task='TrueOrochi', success=False, finish=False, server=False, target=datetime.now())
        # 记得关掉
        if config.orochi_config.soul_buff_enable:
            self.goto_page(page_main)
            self.open_buff()
            self.soul(is_open=False)
            self.close_buff()
        # 只有达到副本限制才结束当前周期；中途错误则短延迟重试并保留进度。
        cycle_finished = self.current_count >= self.limit_count or \
            datetime.now() - self.start_time >= self.limit_time
        if cycle_finished:
            self.config._orochi_cycle_state = None
            self.set_next_run('Orochi', finish=True, success=True)
        else:
            cycle_state['count'] = self.current_count
            self.set_next_run(
                'Orochi',
                server=False,
                target=datetime.now().replace(microsecond=0) + timedelta(seconds=30),
            )

        raise TaskEnd


    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        # 同时接受完整名称和资源中的单字名称，不把任意 OCR 文本截成首字。
        aliases = {item.value: item.value[0] for item in Layer}
        aliases.update({item.value[0]: item.value[0] for item in Layer})
        layer_name = layer.value if isinstance(layer, Layer) else layer
        target = aliases.get(''.join(layer_name.split()))
        if target is None:
            raise ValueError(f'Unknown Orochi layer: {layer_name}')
        order = [item.value[0] for item in Layer]
        target_index = order.index(target)
        roi = self.L_LAYER_LIST.roi_back
        ocr = RuleOcr(roi=roi, area=(0, 0, 10, 10), mode='Full', method='Default',
                      keyword=target, name='orochi_layer')
        swipes = 0
        misses = 0
        unchanged = 0
        previous = None
        while 1:
            self.screenshot()
            visible = []
            for result in ocr.detect_and_ocr(self.device.image):
                name = aliases.get(''.join(result.ocr_text.split()))
                if name is None or result.score <= RuleOcr.score:
                    continue
                visible.append(order.index(name))
                if name == target:
                    box = result.box
                    x = int(roi[0] + (box[0, 0] + box[1, 0]) / 2)
                    y = int(roi[1] + (box[0, 1] + box[2, 1]) / 2)
                    if roi[0] <= x < roi[0] + roi[2] and roi[1] <= y < roi[1] + roi[3]:
                        logger.info(f'Orochi layer {layer_name} found: {result.ocr_text}')
                        self.device.click(x=x, y=y)
                        return True
            # 无可靠定位时只重试识别，不能把空结果当成 (0, 0) 点击或盲目滑动。
            if not visible or min(visible) <= target_index <= max(visible):
                misses += 1
                if misses >= 3:
                    raise GameStuckError(f'Cannot recognize Orochi layer: {layer_name}')
                sleep(0.5)
                continue
            misses = 0
            current = tuple(sorted(set(visible)))
            unchanged = unchanged + 1 if current == previous else 0
            if swipes >= 6 or unchanged >= 2:
                raise GameStuckError(f'Cannot locate Orochi layer {layer_name} after {swipes} swipes')
            previous = current
            # ROI 是 x/y/宽/高；使用列表内部的中心点，避免滑到列表左侧。
            center_x = roi[0] + roi[2] // 2
            center_y = roi[1] + roi[3] // 2
            half_distance = min(self.L_LAYER_LIST.size[1], roi[3] // 4)
            start_y, end_y = center_y + half_distance, center_y - half_distance
            if target_index < min(visible):
                start_y, end_y = end_y, start_y
            self.device.swipe(p1=(center_x, start_y), p2=(center_x, end_y))
            swipes += 1
            sleep(random.uniform(0.8, 1.3))

    def check_lock(self, lock: bool = True) -> bool:
        """
        检查是否锁定阵容, 要求在八岐大蛇界面
        :param lock:
        :return:
        """
        logger.info('Check lock: %s', lock)
        if lock:
            while 1:
                self.screenshot()
                if self.appear(self.I_OROCHI_LOCK):
                    return True
                if self.appear_then_click(self.I_OROCHI_UNLOCK, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_OROCHI_UNLOCK):
                    return True
                if self.appear_then_click(self.I_OROCHI_LOCK, interval=1):
                    continue











    def run_leader(self):
        logger.info('Start run leader')
        self.goto_page(page_orochi)
        layer = self.config.orochi.orochi_config.layer
        self.check_layer(layer)
        # https://github.com/runhey/OnmyojiAutoScript/issues/592
        self.config.orochi.general_battle_config.lock_team_enable = True
        self.check_lock(self.config.orochi.general_battle_config.lock_team_enable)
        # 创建队伍
        logger.info('Create team')
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_TEAM):
                break
            if self.appear_then_click(self.I_FORM_TEAM, interval=1):
                continue
        # 创建房间
        self.create_room()
        self.ensure_private()
        self.create_ensure()

        # 邀请队友
        success = True
        is_first = True
        # 这个时候我已经进入房间了哦
        while 1:
            self.screenshot()
            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            if self.check_and_invite(self.config.orochi.invite_config.default_invite):
                continue

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if self.current_count >= self.limit_count:
                if self.is_in_room():
                    logger.info('Orochi count limit out')
                    break

            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room():
                    logger.info('Orochi time limit out')
                    break



            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room():
                if self.is_room_dead():
                    logger.warning('Orochi task failed')
                    success = False
                    break
                continue

            # 点击挑战
            if not is_first:
                if self.run_invite(config=self.config.orochi.invite_config):
                    self.run_general_battle(config=self.config.orochi.general_battle_config)
                else:
                    # 邀请失败，退出任务
                    logger.warning('Invite failed and exit this orochi task')
                    success = False
                    break

            # 第一次会邀请队友
            if is_first:
                if not self.run_invite(config=self.config.orochi.invite_config, is_first=True):
                    logger.warning('Invite failed and exit this orochi task')
                    success = False
                    break
                else:
                    is_first = False
                    self.run_general_battle(config=self.config.orochi.general_battle_config)

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass

        self.goto_page(page_main)

        if not success:
            return False
        return True

    def run_member(self):
        logger.info('Start run member')
        # self.ui_goto(page_soul_zones)
        # self.check_lock(self.config.orochi.general_battle_config.lock_team_enable)

        # 队员可能残留在上一次任务的旧房间，必须先退出再等待新邀请。
        self.screenshot()
        if self.is_in_room(is_screenshot=False):
            logger.warning('Member starts in an existing room, leave it before waiting for invite')
            self.exit_room()

        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if self.current_count >= self.limit_count:
                logger.info('Orochi count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('Orochi time limit out')
                break

            if self.check_then_accept():
                continue

            if self.is_in_room():
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self.config.orochi.invite_config.wait_time):
                    self.run_general_battle(config=self.config.orochi.general_battle_config)
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            elif self.check_take_over_battle(False, config=self.config.orochi.general_battle_config):
                continue

        while 1:
            # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
            if self.appear(self.I_CHECK_MAIN) or self.appear(self.I_CHECK_EXPLORATION):
                break
            # 如果可能在房间就退出
            if self.exit_room():
                pass
            # 如果还在战斗中，就退出战斗
            if self.exit_battle():
                pass


        self.goto_page(page_main)
        return True

    def run_alone(self):
        logger.info('Start run alone')
        self.goto_page(page_orochi)
        layer = self.config.orochi.orochi_config.layer
        self.check_layer(layer)
        self.check_lock(self.config.orochi.general_battle_config.lock_team_enable)

        def is_in_orochi(screenshot=False) -> bool:
            if screenshot:
                self.screenshot()
            return self.appear(self.I_OROCHI_FIRE)

        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if not is_in_orochi():
                continue

            if self.current_count >= self.limit_count:
                logger.info('Orochi count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('Orochi time limit out')
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_OROCHI_FIRE, interval=1):
                    pass

                if not self.appear(self.I_OROCHI_FIRE):
                    self.run_general_battle(config=self.config.orochi.general_battle_config)
                    break

        # 回去
        while 1:
            self.screenshot()
            if not self.appear(self.I_FORM_TEAM):
                break
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue

        self.goto_page(page_main)

    def run_wild(self):
        logger.info('Start run wild')

        # 已经在战斗中不必初始化，保证已经组队开始战斗的情况下可以自动执行后续任务
        if not self.is_in_battle(True):
            self.goto_page(page_orochi)
            layer = self.config.orochi.orochi_config.layer
            self.check_layer(layer)
            self.check_lock(self.config.orochi.general_battle_config.lock_team_enable)
            # 创建队伍
            logger.info('Create team')
            while 1:
                self.screenshot()
                if self.appear(self.I_CHECK_TEAM):
                    break
                if self.appear_then_click(self.I_FORM_TEAM, interval=1):
                    continue
            # 创建房间
            self.create_room()
            self.ensure_public()
            self.create_ensure()

        success = True
        while 1:
            self.screenshot()
            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            if self.check_and_invite(self.config.orochi.invite_config.default_invite):
                continue

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if self.current_count >= self.limit_count:
                if self.is_in_room():
                    logger.info('Orochi count limit out')
                    break

            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room():
                    logger.info('Orochi time limit out')
                    break

            if not self.is_in_room():
                if self.is_room_dead():
                    logger.warning('Orochi task failed')
                    success = False
                    break
                continue

            # 点击挑战
            logger.info('Wait for starting')
            while 1:
                self.screenshot()
                # 在进入战斗前必然会出现挑战界面，因此点击失败必须重复点击，防止卡在挑战界面，
                # 点击成功后如果网络卡顿，导致没有进入战斗，则无法进入 run_general_battle 流程，
                # 所以如果判断是在战斗中，则执行通用战斗流程
                if not self.is_in_battle(False):
                    if not self.is_in_room() and self.is_room_dead():
                        break
                    if not self.appear_then_click(self.I_OROCHI_WILD_FIRE, interval=1, threshold=0.8):
                        continue

                self.screenshot()
                if not self.appear(self.I_OROCHI_WILD_FIRE, threshold=0.8):
                    self.run_general_battle(config=self.config.orochi.general_battle_config)
                    break

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass

        self.goto_page(page_main)

        if not success:
            return False
        return True

    def is_room_dead(self) -> bool:
        # 如果在探索界面或者是出现在组队界面，那就是可能房间死了
        sleep(0.5)
        if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
            sleep(0.5)
            if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                return True
        return False

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        重写战斗等待
        # https://github.com/runhey/OnmyojiAutoScript/issues/95
        :param random_click_swipt_enable:
        :return:
        """
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'
        reward_targets = (self.I_REWARD, self.I_REWARD_GOLD, self.I_REWARD_GOLD_SNAKE_SKIN)

        def clear_rewards() -> bool:
            # 奖励页可能有多页，但不能在模板误匹配时无限点击同一控件。
            reward_clicks = 0
            deadline = monotonic() + 20
            exit_targets = (self.I_UI_CONFIRM, self.I_I_ACCEPT, self.I_OROCHI_FIRE,
                            self.I_CHECK_EXPLORATION, self.I_CHECK_TEAM)
            while 1:
                self.screenshot()
                if self.is_in_room(is_screenshot=False) or \
                        self.is_in_prepare(is_screenshot=False) or \
                        self.is_in_real_battle(is_screenshot=False) or \
                        any(self.appear(target) for target in exit_targets):
                    return True
                if monotonic() >= deadline:
                    raise GameStuckError('Orochi reward settlement did not finish within 20 seconds')
                if reward_clicks >= 6:
                    logger.warning('Orochi reward settlement click limit reached, leave reward page')
                    return True
                # 御魂溢出弹窗保留原有处理。
                if self.appear_then_click(self.I_OVER_GHOST, interval=1.5):
                    continue
                reward_visible = self.appear(self.I_GREED_GHOST) or \
                    any(self.appear(target) for target in reward_targets)
                if not reward_visible:
                    continue
                # 奖励页底部是“点击屏幕继续”区域，避免点击左侧奖励/御魂区域。
                if self.click(self.C_REWARD_1, interval=1.5):
                    reward_clicks += 1
                    logger.info(f'Reward settlement click {reward_clicks}/6')

        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
            if self.appear_then_click(self.I_WIN, action=action_click ,interval=0.8):
                # 赢的那个鼓
                continue
            if self.appear(self.I_GREED_GHOST):
                # 贪吃鬼
                logger.info('Win battle')
                self.wait_until_appear(self.I_REWARD, wait_time=1.5)
                self.screenshot()
                if not self.appear(self.I_GREED_GHOST):
                    logger.warning('Greedy ghost disappear. Maybe it is a false battle')
                    continue
                return clear_rewards()
            if any(self.appear(target) for target in reward_targets):
                # 御魂、金币和金蛇皮可能分多页结算。
                logger.info('Win battle')
                return clear_rewards()

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

    def orochi_switch_soul(self) -> None:
        # 判断是否开启根据选层切换御魂
        orochi_switch_soul = self.config.orochi.switch_soul
        if not orochi_switch_soul.auto_switch_soul:
            return

        group_team: str = None
        layer = self.config.orochi.orochi_config.layer
        match layer:
            case Layer.TEN:
                group_team = orochi_switch_soul.ten_switch
            case Layer.ELEVEN:
                group_team = orochi_switch_soul.eleven_switch
            case Layer.TWELVE:
                group_team = orochi_switch_soul.twelve_switch
            case Layer.THIRTEEN:
                group_team = orochi_switch_soul.thirteen_switch

        if orochi_switch_soul.auto_switch_soul:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(group_team)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()








