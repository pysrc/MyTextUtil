package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"net"
	"net/http"
	"os"
	"time"
)

type MyRequest struct {
	Pwd string
	Txt string
}

//使用PKCS7进行填充
func PKCS7Padding(ciphertext []byte, blockSize int) []byte {
	padding := blockSize - len(ciphertext)%blockSize
	padtext := bytes.Repeat([]byte{byte(padding)}, padding)
	return append(ciphertext, padtext...)
}

//aes加密，填充秘钥key的16位，24,32分别对应AES-128, AES-192, or AES-256.
func AesCBCEncrypt(rawData, key, iv []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		panic(err)
	}

	//填充原文
	blockSize := block.BlockSize()
	rawData = PKCS7Padding(rawData, blockSize)
	//初始向量IV必须是唯一，但不需要保密
	cipherText := make([]byte, blockSize+len(rawData))

	//block大小和初始向量大小一定要一致
	mode := cipher.NewCBCEncrypter(block, iv)
	mode.CryptBlocks(cipherText[blockSize:], rawData)

	return cipherText, nil
}

func PKCS7UnPadding(origData []byte) []byte {
	length := len(origData)
	unpadding := int(origData[length-1])
	return origData[:(length - unpadding)]
}

func EncryptToHexString(rawData, key, iv []byte) (string, error) {
	s, err := AesCBCEncrypt(rawData, key, iv)
	// return strings.TrimLeft(hex.EncodeToString(s), "0"), err
	return hex.EncodeToString(s), err
}

func GetKeyIv(pwd string) ([]byte, []byte) {
	has := md5.Sum([]byte(pwd))
	pwd = fmt.Sprintf("%x", has)
	return []byte(pwd[:16]), []byte(pwd[16:])
}

func AesCBCDncrypt(encryptData, key, iv []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		panic(err)
	}

	blockSize := block.BlockSize()

	if len(encryptData) < blockSize {
		panic("ciphertext too short")
	}
	// iv := encryptData[:blockSize]
	encryptData = encryptData[blockSize:]

	// CBC mode always works in whole blocks.
	if len(encryptData)%blockSize != 0 {
		panic("ciphertext is not a multiple of the block size")
	}

	mode := cipher.NewCBCDecrypter(block, iv)

	// CryptBlocks can work in-place if the two arguments are the same.
	mode.CryptBlocks(encryptData, encryptData)
	//解填充
	encryptData = PKCS7UnPadding(encryptData)
	return encryptData, nil
}

// 维持心跳
func Heart(port string) {
	udpAddr, _ := net.ResolveUDPAddr("udp4", "0.0.0.0:"+port)
	udpConn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		fmt.Println(err)
	}
	defer udpConn.Close()
	buf := make([]byte, 2)
	for {
		// 2 秒没收到心跳就超时
		udpConn.SetReadDeadline(time.Now().Add(time.Second * 2))
		_, _, err := udpConn.ReadFromUDP(buf)
		if err != nil {
			os.Exit(0)
		}
	}
}

func main() {
	var port string
	var eport string
	flag.StringVar(&port, "p", "9236", "The server port.")
	flag.StringVar(&eport, "e", "7774", "Heartbeat receiving port.")
	flag.Parse()
	go Heart(eport)
	http.HandleFunc("/exit", func(w http.ResponseWriter, r *http.Request) {
		os.Exit(0)
	})
	http.HandleFunc("/aes-en", func(w http.ResponseWriter, r *http.Request) {
		var req MyRequest
		byt, _ := ioutil.ReadAll(r.Body)
		rb, err := hex.DecodeString(string(byt))
		if err != nil {
			return
		}
		if json.Unmarshal(rb, &req) != nil {
			return
		}
		k, i := GetKeyIv(req.Pwd)
		body, _ := hex.DecodeString(req.Txt)
		en, _ := EncryptToHexString(body, k, i)
		w.Write([]byte(en))
	})
	http.HandleFunc("/aes-de", func(w http.ResponseWriter, r *http.Request) {
		var req MyRequest
		byt, _ := ioutil.ReadAll(r.Body)
		rb, err := hex.DecodeString(string(byt))
		if err != nil {
			return
		}
		if json.Unmarshal(rb, &req) != nil {
			return
		}
		k, i := GetKeyIv(req.Pwd)
		en, err := hex.DecodeString(req.Txt)
		if err != nil {
			return
		}
		btsr, err := AesCBCDncrypt(en, k, i)
		if err != nil {
			return
		}
		w.Write(btsr)
	})
	http.ListenAndServe("0.0.0.0:"+port, nil)
}
