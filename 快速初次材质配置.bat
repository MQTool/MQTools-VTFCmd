@echo off
setlocal enabledelayedexpansion

rem ��ȡ��ǰ�ļ��е�����·��
set "current_path=%cd%"

rem ���·�����Ƿ����"materials"
echo !current_path! | findstr /i "materials" >nul
if errorlevel 1 (
    echo ���󣺵�ǰ·��������"materials"�ļ���
    exit /b 1
)

rem ��ȡ"materials"֮���·������
for /f "tokens=*" %%a in ('echo !current_path! ^| powershell -command "$input | ForEach-Object {$_ -replace '.*\\materials\\', ''}"') do (
    set "after_materials=%%a"
)

if "!after_materials!"=="" (
    echo �����޷���ȡ"materials"֮���·��
    exit /b 1
)

rem ����б���滻Ϊ��б�ܲ�ȥ������ո�
set "after_materials=!after_materials:\=/!"
for /f "tokens=*" %%a in ('echo !after_materials! ^| powershell -command "$input | ForEach-Object {$_.Trim()}"') do (
    set "after_materials=%%a"
)

echo ��ǰ·����!current_path!
echo Materials֮���·����!after_materials!

rem ����shader�ļ���
if not exist "shader" (
    mkdir "shader"
    echo �Ѵ���shader�ļ���
)

rem ����vmt-base.vmt�ļ�
(
    echo "VertexLitGeneric"
    echo {
    echo 	"$basetexture" "basetexture"
    echo 	//"$bumpmap"					"normal"	// ������ͼ��û���õ��Ͳ�Ҫ���á�
    echo 																	// �ر�أ�������ν��ɫ������ͼ���ܻᵼ�� UV ��Ե���ֹ����쳣��
    echo.
    echo 	"$lightwarptexture" 			"diyu2025\UMA\Almond_Eye\shader\toon_light"			// ɫ��У��������Ԫ�ؼӡ����Ƽ����ƣ�һ����и�ʽ���⵼��Ч���쳣��
    echo.
    echo     "$nocull" 						"1"			// ˫����Ⱦ������ģ��������������¶�Ļ���һ�㶼����ģ�͵ı߷�©ɫ���ؿ��Թء�
    echo 	"$nodecal" 						"1"			// ������ֹ���ر�Ѫ�������Է�ֹһЩ�������ˡ�
    echo 	"$phong" 						"1"			// ���Ϸ��俪�ء���͸�����ȫϢ����Թء�
    echo 	"$halflambert" 					"1"			// �������ع��ա��ù��չ��ɸ�����Ȼ���ؿ���
    echo.
    echo 	"$phongboost"					".04"       // ���Ϸ������ȡ���������ȡ���ڷ�����ͼ��Aͨ����Խ����Խ����
    echo 												// ��Ϊ�˽������޸��˸�ͨ������ֵӦ��Ҫ��һ�����ӣ��ο��� 100 ���� .04 �� 4 ��
    echo 												// ���� $phongexponenttexture ֮����ֵ������Ҫ��һ�����ӣ��ο��� 20 ���� 4 �� 80 ����
    echo.	
    echo 	//"$phongexponenttexture"		"ko/vrc/lime/def/ppp_exp"		// �����ܶ���ͼ / �߹���ͼ��ԭ���Ϊ���ӣ�����ĵ���һ�㲻���á�
    echo 																	// Ϊ���� $phongalbedotint��������ν��ɫ�߹���ͼ�����ǿ��Խ��ܵġ�
    echo.														
    echo 	"$phongalbedotint"				"1" 				// ����ɫ��ͼ���ַ��Ϸ�����ɫ���������� $phongexponenttexture ����Ч��Ч������ϸ�۲졣
    echo 	//"$phongexponent" 				"5.0" 				// ���Ϸ����ܶȡ����ú󽫸��� $phongexponenttexture��Ĭ�ϼ�5.0��һ�㲻���޸ġ�
    echo 	//"$phongtint" 					"[1 1 1]" 			// ȫ�ַ��Ϸ���ͨ��ǿ�ȡ����ú󽫸��� $phongalbedotint��Ϊ������ϵ��ֻ�ܵ�ɫ��
    echo 	"$phongfresnelranges"			"[1 .1 .1]" 		// ���Ϸ��������������ԭ���Ϊ���ӣ�����ĵ�����Ҫ�ҵ���
    echo.
    echo 	//"$envmap"						"env_cubemap" 		// ���淴�䡣�ͷ��Ϸ��䲻ͬ����������ͼλ�ö������Դ�йء�����������Ҫ����
    echo 	"$normalmapalphaenvmapmask"		"1" 				// ��������ͼ A ͨ����Ϊ���淴���ɰ档���淴��Ч�����ֽ�ȡ���ڷ�����ͼ��Aͨ����Խ��Խ�������������á�
    echo 	"$envmapfresnel"				"1" 				// ���þ��淴�������Ч������ֵ������Ϸ���������������˷�����Ҫ�ҵ���
    echo 	"$envmaptint"					"[ 0.4 0.4 0.4 ]" 	// ���淴��ͨ��ǿ�ȡ�����Խ�󣬾��淴��Խ���ԡ�����Ϊ������ϵ�����Ե�ɫ��
    echo.
    echo 	//"$selfillum" 					"1" 				// �����Է��⡣��������ȡ������ɫ��ͼ�� A ͨ����Խ����Խ���������Է������ص���
    echo 	//"$selfillummask"                "diyu2024/share/selfillum/mask"         //�Է���ͨ����������ʹ��A͸���������ҹ�⹲�档
    echo 	//"$additive"					"1"					// ������ɫ���ӣ����а�͸��Ч����͸���̶�����ȡ������ɫ��ͼ�� RGB ͨ�����Ҷȣ�����ɫΪ��ȫ͸����
    echo 														// �����Է���һͬ��������������ȫϢ��Ч����
    echo 	//"$translucent"				"1" 				// ������͸����͸���̶�����ȡ������ɫ��ͼ�� A ͨ����Խ����Խ��͸�������Է����ͻ��
    echo 	//"$alpha" 						"0.5" 				// ͸�������š���͸��Ч������Ӱ����ӰЧ����
    echo 														// �ر�أ�ͨ�����ʴ���Ӱ��ò���ʱ���ֵ���Ӱ����ʧЧ��
    echo.
    echo.
    echo 	// �ĵ���https://developer.valvesoftware.com/wiki/$phong/en // ���Ϸ���
    echo }
) > "shader\vmt-base.vmt"
echo �Ѵ���shader\vmt-base.vmt�ļ�

rem ����lightwarptexture·��ʹ�õ�ǰ���ʵ�·������ʹ����BOM��UTF-8���뱣��
powershell -command "$content = Get-Content 'shader\vmt-base.vmt' -Raw; $content = $content -replace 'diyu2025\\UMA\\Almond_Eye', '!after_materials!'; $content = $content -replace '\\', '/'; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllText('shader\vmt-base.vmt', $content, $Utf8NoBomEncoding)"
echo �Ѹ���shader\vmt-base.vmt�е�·��

rem ��������vtf�ļ���������Ӧ��vmt�ļ�
set "count=0"
set "eye_count=0"
for %%f in (*.vtf) do (
    set /a "count+=1"
    set "vtf_file=%%~nf"
    
    echo �����ļ���%%f
    
    rem �������eye�ļ����򴴽���ͨ��vmt�ļ�
    if /i not "!vtf_file!"=="eye" (
        (
            echo patch
            echo {
            echo 	include	"materials/!after_materials!/shader/vmt-base.vmt"
            echo 	insert
            echo 	{
            echo 	}
            echo 	replace
            echo 	{
            echo 	"$basetexture" "!after_materials!/!vtf_file!"
            echo }
            echo }
        ) > "!vtf_file!.vmt"
        
        echo �Ѵ�����!vtf_file!.vmt
    ) else (
        rem ��⵽eye�ļ������������vmt�ļ�
        set /a "eye_count+=1"
        set /a "count-=1"
        echo ��⵽eye�ļ������������eye_r.vmt��eye_l.vmt��shader\eye_base.vmt�ļ�...
        
        rem ����eye_base.vmt�ļ���shader�ļ�����
        (
            echo "EyeRefract"
            echo {
            echo 	"$iris" 			  "!after_materials!/eye"	  //������ͼ·��
            echo 	"$AmbientOcclTexture" "!after_materials!/ambient"  // RGB�Ļ����ڵ���Alphaδʹ��
            echo 	"$Envmap"             "Engine/eye-reflection-cubemap-"   		  // Reflection environment map
            echo 	"$CorneaTexture"      "Engine/eye-cornea"                 		  // Special texture that has 2D cornea normal in RG and other data in BA
            echo 	"$EyeballRadius" "0.5"				// Ĭ�� 0.5
            echo 	"$AmbientOcclColor" "[0.1 0.1 0.1]"	// Ĭ�� 0.33, 0.33, 0.33
            echo 	"$Dilation" "0.5"					// Ĭ�� 0.5
            echo 	"$ParallaxStrength" "0.30"          // Ĭ�� 0.25
            echo 	"$CorneaBumpStrength" "0.5"			// Ĭ�� 1.0
            echo 	"$NoDecal" "1"
            echo 	// ��ЩЧ������ps.2.0b���Ժ�汾�п���
            echo 	"$RaytraceSphere" "0"	 // Ĭ�� 1 - ��������ɫ�������ù���׷�٣�ʹ�������ܿ�
            echo 	"$SphereTexkillCombo" "0"// Ĭ�� 1 - Enables killing pixels that don't ray-intersect the sphere
            echo 	"$lightwarptexture" 			"!after_materials!/shader/toon_light"
            echo 	"$EmissiveBlendEnabled" 		"1"
            echo 	"$EmissiveBlendStrength" 		"0.05"
            echo 	"$EmissiveBlendTexture" 		"vgui/white"
            echo 	"$EmissiveBlendBaseTexture" 	"!after_materials!/Eye"
            echo 	"$EmissiveBlendFlowTexture" 	"vgui/white"
            echo 	"$EmissiveBlendTint" 			" [ 1 1 1 ] "
            echo 	"$EmissiveBlendScrollVector" 	" [ 0 0 ] "
            echo }
        ) > "shader\eye_base.vmt"
        
        rem ʹ��PowerShellȷ��eye_base.vmtʹ����BOM��UTF-8����
        powershell -command "$content = Get-Content 'shader\eye_base.vmt' -Raw; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllText('shader\eye_base.vmt', $content, $Utf8NoBomEncoding)"
        echo �Ѵ���shader\eye_base.vmt�ļ�
        
        rem ����eye_r.vmt��eye_l.vmt��ʹ��eye_base.vmt��Ϊinclude
        (
            echo patch
            echo {
            echo 	include	"materials/!after_materials!/shader/eye_base.vmt"
            echo 	insert
            echo 	{
            echo 	}
            echo 	replace
            echo 	{
            echo 	"$iris" "!after_materials!/!vtf_file!"
            echo 	}
            echo }
        ) > "!vtf_file!_r.vmt"
        
        (
            echo patch
            echo {
            echo 	include	"materials/!after_materials!/shader/eye_base.vmt"
            echo 	insert
            echo 	{
            echo 	}
            echo 	replace
            echo 	{
            echo 	"$iris" "!after_materials!/!vtf_file!"
            echo 	}
            echo }
        ) > "!vtf_file!_l.vmt"
        
        echo �Ѵ�����!vtf_file!_r.vmt
        echo �Ѵ�����!vtf_file!_l.vmt
    )
)

echo ������ɣ��������� !count! ����ͨVMT�ļ���
if !eye_count! gtr 0 (
    echo �����⵽ !eye_count! ��eye�ļ�����Ϊ�䴴��������������VMT�ļ���shader\eye_base.vmt��
)
pause 