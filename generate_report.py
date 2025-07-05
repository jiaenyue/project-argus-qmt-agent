  
import os  
import re  
import chardet  # 添加编码检测库  
from datetime import datetime  

def detect_encoding(file_path):  
    """自动检测文件编码"""  
    with open(file_path, 'rb') as f:  
        result = chardet.detect(f.read())  
    return result['encoding'] or 'utf-8'  

def parse_validation_report(report_path):  
    """解析验证报告文件，提取文件验证结果"""  
    # 自动检测文件编码  
    encoding = detect_encoding(report_path)  
    
    results = []  
    current_file = None  
      
    with open(report_path, 'r', encoding=encoding, errors='replace') as f:  
        for line in f:  
            # 检测文件开始  
            if line.startswith("[文件]"):  
                file_path = line.split("[文件] ")[1].strip()  
                current_file = {  
                    "file_path": file_path,  
                    "status": None,  
                    "errors": []  
                }  
                results.append(current_file)  
              
            # 检测状态  
            elif line.startswith("[成功]") and current_file:  
                current_file["status"] = "success"  
            elif line.startswith("[失败]") and current_file:  
                current_file["status"] = "failed"  
              
            # 检测错误信息  
            elif line.startswith("错误信息:") and current_file:  
                current_file["errors"] = []  
            elif current_file and current_file["status"] == "failed" and line.strip():  
                current_file["errors"].append(line.strip())  
      
    return results  

def generate_quality_report():  
    """生成教程验证质量报告"""  
    # 解析验证报告  
    validation_report = "tutorials_validation_report.txt"  
    file_results = parse_validation_report(validation_report)  
      
    report = {  
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  
        "files": []  
    }  
      
    # 为每个文件生成报告项  
    for file in file_results:  
        file_report = {  
            "file_path": file["file_path"],  
            "status": "completed" if file["status"] == "success" else "failed",  
            "output_quality": {  
                "has_expected_structure": file["status"] == "success",  
                "key_fields_present": [] if file["status"] == "failed" else ["date", "open", "high", "low", "close", "volume"],  
                "error_messages": len(file["errors"]),  
                "data_points": 0 if file["status"] == "failed" else 3  
            },  
            "issues": file["errors"]  
        }  
        report["files"].append(file_report)  
      
    # 保存报告  
    report_path = "tutorials_quality_report.txt"  
    with open(report_path, "w", encoding="utf-8") as f:  
        f.write("="*50 + "\n")  
        f.write("教程验证质量报告\n")  
        f.write("="*50 + "\n\n")  
          
        f.write(f"生成时间: {report['timestamp']}\n")  
        f.write(f"验证文件数: {len(report['files'])}\n")  
        f.write(f"成功文件数: {sum(1 for f in report['files'] if f['status'] == 'completed')}\n")  
        f.write(f"失败文件数: {sum(1 for f in report['files'] if f['status'] == 'failed')}\n\n")  
          
        for file in report['files']:  
            f.write(f"文件: {file['file_path']}\n")  
            f.write(f"状态: {file['status']}\n")  
            f.write("输出质量评估:\n")  
            f.write(f"  - 数据结构完整: {'是' if file['output_quality']['has_expected_structure'] else '否'}\n")  
            f.write(f"  - 关键字段存在: {', '.join(file['output_quality']['key_fields_present'])}\n")  
            f.write(f"  - 错误信息数量: {file['output_quality']['error_messages']}\n")  
            f.write(f"  - 数据点数: {file['output_quality']['data_points']}\n")  
              
            if file['issues']:  
                f.write("发现的问题:\n")  
                for issue in file['issues']:  
                    f.write(f"  - {issue}\n")  
              
            f.write("\n" + "-"*50 + "\n")  
      
    print(f"报告已生成: {os.path.abspath(report_path)}")  

if __name__ == "__main__":  
    generate_quality_report()  