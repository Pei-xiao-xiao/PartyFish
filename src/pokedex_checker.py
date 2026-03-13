"""
图鉴完整性检查脚本
检查 fish.json 和 resources/fish/ 图片文件的一致性
"""

import json
from pathlib import Path
from src.config import cfg


def check_pokedex_completeness():
    """检查图鉴完整性"""

    # 加载 fish.json
    fish_json_path = cfg._get_base_path() / "resources" / "fish.json"
    with open(fish_json_path, encoding="utf-8") as f:
        fish_data = json.load(f)

    # 获取鱼类名称列表
    fish_names_json = {fish["name"] for fish in fish_data}
    print(f"📋 fish.json 中鱼类数量：{len(fish_names_json)}")

    # 获取图片文件列表
    fish_dir = cfg._get_base_path() / "resources" / "fish"
    image_files = {f.stem for f in fish_dir.glob("*.png")}
    print(f"🖼️  鱼类图片数量：{len(image_files)}")

    # 查找差异
    missing_images = fish_names_json - image_files
    missing_fish = image_files - fish_names_json

    print("\n" + "=" * 60)
    print("🔍 检查结果")
    print("=" * 60)

    print("\n❌ 缺少图片的鱼类:")
    if missing_images:
        for name in sorted(missing_images):
            print(f"   - {name}")
        print(f"   共计：{len(missing_images)} 种")
    else:
        print("   ✅ 所有鱼类都有对应的图片")

    print("\n❓ 有图片但不在 fish.json 中的鱼类:")
    if missing_fish:
        for name in sorted(missing_fish):
            print(f"   - {name}")
        print(f"   共计：{len(missing_fish)} 种")
    else:
        print("   ✅ 所有图片都在 fish.json 中有对应记录")

    # 检查 show_in_pokedex 属性
    pokedex_fish = {
        fish["name"] for fish in fish_data if fish.get("show_in_pokedex", True)
    }
    hidden_fish = {
        fish["name"] for fish in fish_data if not fish.get("show_in_pokedex", True)
    }

    print("\n" + "=" * 60)
    print("📊 图鉴显示统计")
    print("=" * 60)
    print(f"   图鉴显示鱼类：{len(pokedex_fish)} 种")
    print(f"   隐藏鱼类：{len(hidden_fish)} 种")

    if hidden_fish:
        print("\n   隐藏鱼类列表:")
        for name in sorted(hidden_fish):
            print(f"      - {name}")

    # 检查图鉴收集进度
    print("\n" + "=" * 60)
    print("📈 图鉴收集进度")
    print("=" * 60)

    from src.pokedex import pokedex, QUALITIES

    all_fish = pokedex.get_all_fish()
    total_fish = len(all_fish)
    total_qualities = total_fish * len(QUALITIES)

    collected_fish = 0
    collected_qualities = 0

    for fish in all_fish:
        fish_name = fish.get("name", "")
        status = pokedex.get_collection_status(fish_name)
        fish_collected = sum(1 for v in status.values() if v is not None)

        if fish_collected > 0:
            collected_fish += 1
        collected_qualities += fish_collected

    fish_percentage = (collected_fish / total_fish * 100) if total_fish > 0 else 0
    quality_percentage = (
        (collected_qualities / total_qualities * 100) if total_qualities > 0 else 0
    )

    print(f"   鱼类收集：{collected_fish}/{total_fish} ({fish_percentage:.1f}%)")
    print(
        f"   品质收集：{collected_qualities}/{total_qualities} ({quality_percentage:.1f}%)"
    )

    # 输出报告到文件
    report_path = cfg._get_application_path() / "图鉴检查报告.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("图鉴完整性检查报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"fish.json 中鱼类数量：{len(fish_names_json)}\n")
        f.write(f"鱼类图片数量：{len(image_files)}\n\n")

        f.write("缺少图片的鱼类:\n")
        if missing_images:
            for name in sorted(missing_images):
                f.write(f"  - {name}\n")
            f.write(f"共计：{len(missing_images)} 种\n")
        else:
            f.write("✅ 所有鱼类都有对应的图片\n")

        f.write("\n有图片但不在 JSON 中的鱼类:\n")
        if missing_fish:
            for name in sorted(missing_fish):
                f.write(f"  - {name}\n")
            f.write(f"共计：{len(missing_fish)} 种\n")
        else:
            f.write("✅ 所有图片都在 fish.json 中有对应记录\n")

        f.write(f"\n图鉴显示鱼类：{len(pokedex_fish)} 种\n")
        f.write(f"隐藏鱼类：{len(hidden_fish)} 种\n")
        if hidden_fish:
            f.write("\n隐藏鱼类列表:\n")
            for name in sorted(hidden_fish):
                f.write(f"  - {name}\n")

        f.write("\n" + "=" * 60 + "\n")
        f.write(f"鱼类收集：{collected_fish}/{total_fish} ({fish_percentage:.1f}%)\n")
        f.write(
            f"品质收集：{collected_qualities}/{total_qualities} ({quality_percentage:.1f}%)\n"
        )

    print(f"\n📄 详细报告已保存到：{report_path}")

    return {
        "missing_images": missing_images,
        "missing_fish": missing_fish,
        "total_fish": len(fish_names_json),
        "total_images": len(image_files),
        "hidden_fish": hidden_fish,
    }


if __name__ == "__main__":
    check_pokedex_completeness()
