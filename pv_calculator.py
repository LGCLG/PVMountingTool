"""
光伏支架简易选型与载荷计算工具 (符合GB规范要求)
版本: 2.0
作者: lgc
最后更新: 2025-7-9
"""

import math

# ======================== 规范参数预设 ========================
# 钢材物理参数 (Q235B)
STEEL_DENSITY = 7850  # kg/m³ (钢材密度)
STEEL_YIELD_STRENGTH = 235  # MPa (屈服强度)
SAFETY_FACTOR = 1.5  # 安全系数

# 风荷载体型系数 (根据GB50009-2012表8.3.1简化)
WIND_SHAPE_COEFF = {
    "单坡": 1.3,  # 单坡屋面
    "双坡": 0.9,  # 双坡屋面
    "平顶": 1.0   # 平顶
}

# 城市基本风压/雪压 (kN/m²) 根据GB50009-2012附录E简化
CITY_LOAD_DATA = {
    "北京": {"wind": 0.45, "snow": 0.40},
    "上海": {"wind": 0.55, "snow": 0.20},
    "广州": {"wind": 0.50, "snow": 0.00},
    "哈尔滨": {"wind": 0.55, "snow": 0.45},
    "乌鲁木齐": {"wind": 0.60, "snow": 0.80},
    "拉萨": {"wind": 0.30, "snow": 0.15},
    "默认": {"wind": 0.40, "snow": 0.35}
}

# 常用型钢库 (C型钢和方管) 单位: mm
STEEL_SECTIONS = {
    # C型钢: [高度, 宽度, 卷边, 厚度, 截面面积(cm²), 惯性矩Ix(cm⁴)]
    "C80x40x15x2.0": [80, 40, 15, 2.0, 4.24, 43.92],
    "C100x50x20x2.5": [100, 50, 20, 2.5, 6.78, 112.12],
    "C120x50x20x2.5": [120, 50, 20, 2.5, 7.18, 198.60],
    "C140x50x20x3.0": [140, 50, 20, 3.0, 8.64, 322.55],

    # 方管: [边长, 厚度, 截面面积(cm²), 惯性矩Ix(cm⁴)]
    "□60x60x2.5": [60, 2.5, 5.67, 34.45],
    "□80x80x3.0": [80, 3.0, 8.76, 73.49],
    "□100x100x3.5": [100, 3.5, 13.20, 178.08],
    "□120x120x4.0": [120, 4.0, 18.18, 346.36]
}

# ======================== 输入验证系统 ========================
def get_valid_input(prompt, input_type=float, min_val=None, max_val=None, default=None, max_attempts=3):
    """
    获取用户输入并验证，提供重新输入机会

    参数:
        prompt: 提示文本
        input_type: 输入类型 (float, int, str)
        min_val: 最小值 (可选)
        max_val: 最大值 (可选)
        default: 默认值 (可选)
        max_attempts: 最大尝试次数

    返回:
        验证后的输入值
    """
    attempts = 0
    while attempts < max_attempts:
        try:
            # 显示提示信息，包括范围和默认值
            full_prompt = prompt
            if min_val is not None and max_val is not None:
                full_prompt += f" ({min_val}-{max_val})"
            elif min_val is not None:
                full_prompt += f" (≥{min_val})"
            elif max_val is not None:
                full_prompt += f" (≤{max_val})"

            if default is not None:
                full_prompt += f" [默认: {default}]: "
            else:
                full_prompt += ": "

            # 获取用户输入
            user_input = input(full_prompt).strip()

            # 处理空输入和默认值
            if user_input == "" and default is not None:
                print(f"使用默认值: {default}")
                return default
            elif user_input == "":
                raise ValueError("输入不能为空")

            # 转换为指定类型
            value = input_type(user_input)

            # 验证范围
            if min_val is not None and value < min_val:
                raise ValueError(f"值不能小于 {min_val}")
            if max_val is not None and value > max_val:
                raise ValueError(f"值不能大于 {max_val}")

            return value

        except ValueError as e:
            attempts += 1
            remaining = max_attempts - attempts
            print(f"错误: {str(e)}")
            if remaining > 0:
                print(f"请重新输入 ({remaining}次机会)")
            else:
                print("已达到最大尝试次数")

    # 达到最大尝试次数后使用默认值或抛出异常
    if default is not None:
        print(f"使用默认值: {default}")
        return default
    else:
        raise ValueError(f"无法获取有效的{input_type.__name__}输入")

def get_user_input():
    """获取用户输入参数，带验证和重新输入功能"""
    print("\n" + "="*50)
    print("光伏支架荷载计算与选型工具 (符合GB规范)")
    print("="*50)

    # 项目地点 - 字符串类型
    location = input("项目地点 (如北京、上海，或直接回车使用默认值): ").strip() or "默认"
    if location not in CITY_LOAD_DATA:
        print(f"警告: 未找到'{location}'的风雪压数据，使用默认值")
        location = "默认"

    # 屋面类型 - 带选项验证
    while True:
        roof_type = input("屋面类型 (单坡/双坡/平顶，回车默认平顶): ").strip() or "平顶"
        if roof_type in WIND_SHAPE_COEFF:
            break
        print(f"错误: 无效的屋面类型 '{roof_type}'，请输入: 单坡, 双坡 或 平顶")

    # 数值输入 - 带范围和类型验证
    tilt_angle = get_valid_input(
        prompt="光伏板倾角 (度)",
        input_type=float,
        min_val=0,
        max_val=90,
        default=30.0
    )

    mounting_height = get_valid_input(
        prompt="支架安装高度 (m)",
        input_type=float,
        min_val=0.1,
        max_val=50,
        default=3.0
    )

    pv_length = get_valid_input(
        prompt="单块光伏板长度 (m)",
        input_type=float,
        min_val=0.5,
        max_val=3.0,
        default=1.7
    )

    pv_width = get_valid_input(
        prompt="单块光伏板宽度 (m)",
        input_type=float,
        min_val=0.5,
        max_val=2.0,
        default=1.0
    )

    pv_weight = get_valid_input(
        prompt="单块光伏板重量 (kg)",
        input_type=float,
        min_val=1,
        max_val=50,
        default=20.0
    )

    pv_per_row = get_valid_input(
        prompt="每行光伏板数量",
        input_type=int,
        min_val=1,
        max_val=100,
        default=10
    )

    num_rows = get_valid_input(
        prompt="总行数",
        input_type=int,
        min_val=1,
        max_val=1000,
        default=20
    )

    column_spacing = get_valid_input(
        prompt="立柱间距 (m)",
        input_type=float,
        min_val=0.5,
        max_val=10,
        default=2.5
    )

    span_length = get_valid_input(
        prompt="主梁跨度 (m)",
        input_type=float,
        min_val=1,
        max_val=50,
        default=10.0
    )

    return {
        "location": location,
        "roof_type": roof_type,
        "tilt_angle": tilt_angle,
        "mounting_height": mounting_height,
        "pv_length": pv_length,
        "pv_width": pv_width,
        "pv_weight": pv_weight,
        "pv_per_row": pv_per_row,
        "num_rows": num_rows,
        "column_spacing": column_spacing,
        "span_length": span_length
    }

# ======================== 计算函数 ========================
def calculate_wind_load(params):
    """计算风荷载 (根据GB50009-2012)"""
    try:
        city_data = CITY_LOAD_DATA.get(params["location"], CITY_LOAD_DATA["默认"])
        W0 = city_data["wind"]  # 基本风压 (kN/m²)

        # 风压高度变化系数 (根据GB50009-2012表8.2.1简化)
        # 假设B类地貌 (田野、乡村、丛林)
        height = params["mounting_height"]
        if height <= 5:
            μz = 1.0
        elif height <= 10:
            μz = 1.0
        elif height <= 15:
            μz = 1.14
        else:
            μz = 1.25  # >15m取1.25

        # 风荷载体型系数
        μs = WIND_SHAPE_COEFF.get(params["roof_type"], 1.0)

        # 计算投影面积 (考虑倾角)
        projected_area = math.sin(math.radians(params["tilt_angle"])) * params["pv_length"] * params["pv_width"]

        # 总风荷载标准值 (kN) = βz * μs * μz * W0 * A
        # 简化: βz(风振系数)取1.0
        wind_load = 1.0 * μs * μz * W0 * projected_area * params["pv_per_row"] * params["num_rows"]

        # 考虑风荷载可能为负压(吸力)，取绝对值
        return abs(wind_load)

    except Exception as e:
        print(f"风荷载计算错误: {str(e)}")
        return 0

def calculate_snow_load(params):
    """计算雪荷载 (根据GB50009-2012)"""
    try:
        city_data = CITY_LOAD_DATA.get(params["location"], CITY_LOAD_DATA["默认"])
        S0 = city_data["snow"]  # 基本雪压 (kN/m²)

        # 积雪分布系数 (根据GB50009-2012表7.2.1)
        # 根据倾角确定: 0°~25°取1.0, 25°~50°线性减小到0, >50°取0
        tilt = params["tilt_angle"]
        if tilt <= 25:
            μr = 1.0
        elif tilt <= 50:
            μr = 1.0 - (tilt - 25) / 25
        else:
            μr = 0

        # 总雪荷载标准值 (kN) = μr * S0 * A
        area = params["pv_length"] * params["pv_width"] * math.cos(math.radians(tilt))
        snow_load = μr * S0 * area * params["pv_per_row"] * params["num_rows"]

        return snow_load

    except Exception as e:
        print(f"雪荷载计算错误: {str(e)}")
        return 0

def calculate_dead_load(params):
    """计算恒荷载"""
    try:
        # 光伏板总重
        pv_total_weight = params["pv_weight"] * params["pv_per_row"] * params["num_rows"]

        # 支架自重估算 (按光伏板重量的25%~40%)
        support_weight_factor = 0.3  # 取30%
        support_weight = pv_total_weight * support_weight_factor

        # 转换为荷载 (kN)
        dead_load = (pv_total_weight + support_weight) * 0.0098  # 1kg = 0.0098 kN

        return dead_load

    except Exception as e:
        print(f"恒荷载计算错误: {str(e)}")
        return 0

def calculate_combined_load(dead_load, wind_load, snow_load):
    """荷载组合 (根据GB50009-2012)"""
    try:
        # 组合1: 1.2恒载 + 1.4风载 (主导)
        combo1 = 1.2 * dead_load + 1.4 * wind_load

        # 组合2: 1.2恒载 + 1.4雪载
        combo2 = 1.2 * dead_load + 1.4 * snow_load

        # 组合3: 1.2恒载 + 0.9*1.4*(风载+雪载) (考虑同时作用)
        combo3 = 1.2 * dead_load + 0.9 * 1.4 * (wind_load + snow_load)

        # 取最大值作为设计荷载
        design_load = max(combo1, combo2, combo3)

        return design_load, combo1, combo2, combo3

    except Exception as e:
        print(f"荷载组合计算错误: {str(e)}")
        return 0, 0, 0, 0

def select_column_section(design_load, params):
    """选择立柱截面"""
    try:
        # 计算立柱承受的轴力 (简化为轴心受压)
        # 假设每个立柱承担其影响范围内的荷载
        columns_per_row = math.ceil(params["span_length"] / params["column_spacing"])
        total_columns = columns_per_row * params["num_rows"]

        if total_columns == 0:
            total_columns = 1  # 防止除零错误

        # 单根立柱设计轴力 (kN)
        column_load = design_load / total_columns

        # 转换为压力 (N)
        axial_force = column_load * 1000  # kN -> N

        # 计算所需最小截面面积 (mm²)
        # σ = N / A ≤ f_y / γ = 235 / 1.5 ≈ 157 MPa
        required_area = axial_force / (STEEL_YIELD_STRENGTH / SAFETY_FACTOR)

        # 转换为 cm²
        required_area_cm2 = required_area / 100

        # 在型钢库中选择满足要求的截面
        selected_section = None
        for section, props in STEEL_SECTIONS.items():
            section_area = props[4]  # 截面面积 (cm²)
            if section_area >= required_area_cm2:
                selected_section = section
                break

        # 如果未找到合适的截面，选择最大截面
        if not selected_section:
            selected_section = max(STEEL_SECTIONS.keys(), key=lambda k: STEEL_SECTIONS[k][4])

        return selected_section

    except Exception as e:
        print(f"立柱选型错误: {str(e)}")
        return "□100x100x3.5"  # 默认返回一个常用截面

def calculate_steel_usage(params, column_section):
    """估算钢材用量"""
    try:
        # 计算立柱数量
        columns_per_row = math.ceil(params["span_length"] / params["column_spacing"])
        total_columns = columns_per_row * params["num_rows"]

        # 获取型钢参数
        section_props = STEEL_SECTIONS[column_section]
        section_area_cm2 = section_props[4]  # cm²
        section_area_m2 = section_area_cm2 / 10000  # m²

        # 估算立柱长度 (假设为安装高度的1.2倍)
        column_length = params["mounting_height"] * 1.2

        # 计算立柱总重量 (kg)
        column_weight = section_area_m2 * column_length * STEEL_DENSITY * total_columns

        # 估算主梁重量 (按立柱重量的60%)
        beam_weight = column_weight * 0.6

        # 估算连接件重量 (按总重量的15%)
        connection_weight = (column_weight + beam_weight) * 0.15

        # 总用钢量
        total_steel = column_weight + beam_weight + connection_weight

        return total_steel, column_weight, beam_weight, connection_weight

    except Exception as e:
        print(f"钢材用量计算错误: {str(e)}")
        return 0, 0, 0, 0

def display_results(params, wind_load, snow_load, dead_load, design_load, combo1, combo2, combo3, column_section, total_steel, column_weight, beam_weight, connection_weight):
    """格式化显示计算结果"""
    print("\n" + "="*50)
    print("光伏支架设计计算结果")
    print("="*50)
    print(f"项目地点: {params['location']}")
    print(f"屋面类型: {params['roof_type']}")
    print(f"光伏板倾角: {params['tilt_angle']}°")
    print(f"安装高度: {params['mounting_height']} m")
    print(f"光伏阵列: {params['num_rows']}行 x {params['pv_per_row']}块/行")
    print(f"总光伏面积: {params['pv_length']*params['pv_width']*params['pv_per_row']*params['num_rows']:.2f} m²")
    print("-"*50)
    print("荷载计算结果:")
    print(f"恒荷载 (DL): {dead_load:.2f} kN")
    print(f"风荷载 (WL): {wind_load:.2f} kN")
    print(f"雪荷载 (SL): {snow_load:.2f} kN")
    print(f"荷载组合1 (1.2DL+1.4WL): {combo1:.2f} kN")
    print(f"荷载组合2 (1.2DL+1.4SL): {combo2:.2f} kN")
    print(f"荷载组合3 (1.2DL+0.9*1.4*(WL+SL)): {combo3:.2f} kN")
    print(f"设计荷载 (取最大值): {design_load:.2f} kN")
    print("-"*50)
    print("结构选型结果:")
    print(f"推荐立柱截面: {column_section}")
    print(f"立柱总数: {math.ceil(params['span_length']/params['column_spacing'])*params['num_rows']}")
    print(f"预估总用钢量: {total_steel:.2f} kg")
    print(f"  - 立柱重量: {column_weight:.2f} kg")
    print(f"  - 主梁重量: {beam_weight:.2f} kg")
    print(f"  - 连接件重量: {connection_weight:.2f} kg")
    print("="*50)
    print("注意: 本计算结果为初步估算，实际工程需进行详细结构设计")
    print("="*50)

def main():
    """主程序"""
    while True:
        try:
            # 获取用户输入
            params = get_user_input()

            # 荷载计算
            wind_load = calculate_wind_load(params)
            snow_load = calculate_snow_load(params)
            dead_load = calculate_dead_load(params)

            # 荷载组合
            design_load, combo1, combo2, combo3 = calculate_combined_load(dead_load, wind_load, snow_load)

            # 立柱选型
            column_section = select_column_section(design_load, params)

            # 钢材用量估算
            total_steel, column_weight, beam_weight, connection_weight = calculate_steel_usage(params, column_section)

            # 显示结果
            display_results(params, wind_load, snow_load, dead_load, design_load,
                           combo1, combo2, combo3, column_section,
                           total_steel, column_weight, beam_weight, connection_weight)

            # 询问是否重新计算
            restart = input("\n是否重新计算? (y/n): ").strip().lower()
            if restart != 'y':
                print("\n程序结束，感谢使用！")
                break

            print("\n" + "="*50 + "\n")

        except Exception as e:
            print(f"\n程序运行错误: {str(e)}")
            restart = input("是否重新开始? (y/n): ").strip().lower()
            if restart != 'y':
                print("\n程序结束，感谢使用！")
                break

if __name__ == "__main__":
    main()
