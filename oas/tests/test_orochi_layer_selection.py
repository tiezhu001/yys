"""Replay floor OCR results without importing the GUI or connecting a Device."""

import ast
import random
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load_selection(root=ROOT):
    config = ast.parse((root / 'tasks/Orochi/config.py').read_text(encoding='utf-8-sig'))
    layer = next(node for node in config.body if isinstance(node, ast.ClassDef) and node.name == 'Layer')
    source = ast.parse((root / 'tasks/Orochi/script_task.py').read_text(encoding='utf-8-sig'))
    task = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'ScriptTask')
    selection = next(node for node in task.body if isinstance(node, ast.FunctionDef) and node.name == 'check_layer')
    namespace = dict(Enum=Enum, random=random, sleep=lambda _: None,
                     GameStuckError=SelectionStuck, logger=SimpleNamespace(info=lambda *args: None))
    exec(compile(ast.Module(body=[layer, selection], type_ignores=[]), '<isolated selection>', 'exec'), namespace)
    return namespace


class SelectionStuck(Exception):
    pass


class Box:
    def __init__(self, x, y):
        self.points = ((x, y), (x + 50, y), (x + 50, y + 24), (x, y + 24))

    def __getitem__(self, index):
        row, column = index
        return self.points[row][column]


def result(text, y=20, score=0.99, x=4):
    return SimpleNamespace(ocr_text=text, score=score, box=Box(x, y))


def page(names):
    return [result(name, y=10 + index * 90) for index, name in enumerate(names)]


class Replay:
    def __init__(self, namespace, frames):
        self.frames = frames
        self.shots = 0
        self.clicks = []
        self.swipes = []
        self.L_LAYER_LIST = SimpleNamespace(roi_back=(126, 107, 79, 593), size=(79, 86))
        self.device = SimpleNamespace(image=object(), click=lambda **kw: self.clicks.append(kw),
                                      swipe=lambda **kw: self.swipes.append(kw))

        def reader(**kwargs):
            return SimpleNamespace(detect_and_ocr=lambda image: self.frames[min(self.shots - 1, len(self.frames) - 1)])

        reader.score = 0.6
        namespace['RuleOcr'] = reader
        self.check_layer = lambda layer: namespace['check_layer'](self, layer)

    def screenshot(self):
        self.shots += 1
        if self.shots > 30:
            raise AssertionError('Selection did not terminate')


class OrochiLayerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.namespace = load_selection()
        self.layers = list(self.namespace['Layer'])

    def test_all_layers_accept_enum_full_and_short_input_and_ocr(self):
        for layer in self.layers:
            for requested in (layer, layer.value, layer.value[0]):
                for detected in (layer.value, layer.value[0]):
                    with self.subTest(requested=requested, detected=detected):
                        task = Replay(self.namespace, [[result(detected)]])
                        self.assertTrue(task.check_layer(requested))
                        self.assertEqual(task.clicks, [dict(x=155, y=139)])
                        self.assertEqual(task.swipes, [])

    def test_logged_full_names_find_shenfa_without_swiping(self):
        task = Replay(self.namespace, [page(['柒层', '捌层', '玖层', '拾层', '悲鸣', '神罚'])])
        self.assertTrue(task.check_layer(self.layers[11]))
        self.assertEqual(task.clicks, [dict(x=155, y=579)])
        self.assertEqual(task.swipes, [])

    def test_whitespace_and_mixed_labels(self):
        task = Replay(self.namespace, [page(['柒层', '捌', '玖层', '拾', '悲鸣', ' 神\n罚 '])])
        self.assertTrue(task.check_layer(' 神罚 '))
        self.assertEqual(len(task.clicks), 1)
        self.assertEqual(task.swipes, [])

    def test_transient_empty_ocr_recovers_without_clicking_origin(self):
        task = Replay(self.namespace, [[], [], [result('神罚')]])
        self.assertTrue(task.check_layer('神罚'))
        self.assertEqual(task.clicks, [dict(x=155, y=139)])
        self.assertEqual(task.swipes, [])

    def test_empty_noise_and_low_confidence_stop_without_actions(self):
        for frame in ([], [result('神秘')], [result('神罚奖励')], [result('神罚', score=0.6)]):
            with self.subTest(frame=frame):
                task = Replay(self.namespace, [frame])
                with self.assertRaises(SelectionStuck):
                    task.check_layer('神罚')
                self.assertEqual(task.shots, 3)
                self.assertEqual(task.clicks, [])
                self.assertEqual(task.swipes, [])

    def test_missing_target_between_visible_rows_does_not_scroll(self):
        task = Replay(self.namespace, [page(['悲鸣', '虚无'])])
        with self.assertRaises(SelectionStuck):
            task.check_layer('神罚')
        self.assertEqual(task.swipes, [])
        self.assertEqual(task.clicks, [])

    def test_scrolls_up_and_down_inside_the_list(self):
        for index, initial in ((0, ['柒层', '捌层', '玖层']), (12, ['壹层', '贰层', '叁层'])):
            with self.subTest(index=index):
                task = Replay(self.namespace, [page(initial), [result(self.layers[index].value)]])
                self.assertTrue(task.check_layer(self.layers[index]))
                self.assertEqual(len(task.swipes), 1)
                start, end = task.swipes[0]['p1'], task.swipes[0]['p2']
                for x, y in (start, end):
                    self.assertTrue(126 <= x < 205 and 107 <= y < 700)
                self.assertEqual(start[1] < end[1], index == 0)

    def test_unchanged_list_stops_before_click_watchdog(self):
        task = Replay(self.namespace, [page(['柒层', '捌层', '玖层', '拾层', '悲鸣', '神罚'])])
        with self.assertRaises(SelectionStuck):
            task.check_layer('虚无')
        self.assertEqual(len(task.swipes), 2)
        self.assertEqual(task.clicks, [])

    def test_changing_list_still_has_a_swipe_limit(self):
        task = Replay(self.namespace, [page(['壹层', '贰层']), page(['贰层', '叁层'])] * 4)
        with self.assertRaises(SelectionStuck):
            task.check_layer('虚无')
        self.assertEqual(len(task.swipes), 6)
        self.assertEqual(task.clicks, [])

    def test_out_of_roi_detection_is_never_clicked(self):
        task = Replay(self.namespace, [[result('神罚', x=500)]])
        with self.assertRaises(SelectionStuck):
            task.check_layer('神罚')
        self.assertEqual(task.clicks, [])
        self.assertEqual(task.swipes, [])

    def test_invalid_requested_layer_fails_before_device_use(self):
        task = Replay(self.namespace, [[result('神罚')]])
        with self.assertRaises(ValueError):
            task.check_layer('不存在的层数')
        self.assertEqual(task.shots, 0)


if __name__ == '__main__':
    unittest.main()
