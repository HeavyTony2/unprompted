from torchvision.utils import draw_segmentation_masks
from torchvision.transforms.functional import pil_to_tensor, to_pil_image

class Shortcode():
	def __init__(self,Unprompted):
		self.Unprompted = Unprompted
		self.image_mask = None
		self.show = False
		self.description = "Creates an image mask from the content for use with inpainting."

	def run_block(self, pargs, kwargs, context, content):
		from lib.stable_diffusion.clipseg.models.clipseg import CLIPDensePredT
		from PIL import ImageChops, Image, ImageOps
		import os.path
		import torch
		from torchvision import transforms
		from matplotlib import pyplot as plt
		import cv2
		import numpy
		from modules.images import flatten
		from modules.shared import opts


		if "init_images" not in self.Unprompted.shortcode_user_vars:
			return

		device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

		brush_mask_mode = self.Unprompted.parse_advanced(kwargs["mode"],context) if "mode" in kwargs else "add"
		self.show = True if "show" in pargs else False

		self.legacy_weights = True if "legacy_weights" in pargs else False
		smoothing = int(self.Unprompted.parse_advanced(kwargs["smoothing"],context)) if "smoothing" in kwargs else 20
		smoothing_kernel = None
		if smoothing > 0:
			smoothing_kernel = numpy.ones((smoothing,smoothing),numpy.float32)/(smoothing*smoothing)

		neg_smoothing = int(self.Unprompted.parse_advanced(kwargs["neg_smoothing"],context)) if "neg_smoothing" in kwargs else 20
		neg_smoothing_kernel = None
		if neg_smoothing > 0:
			neg_smoothing_kernel = numpy.ones((neg_smoothing,neg_smoothing),numpy.float32)/(neg_smoothing*neg_smoothing)

		# Pad the mask by applying a dilation or erosion
		mask_padding = int(self.Unprompted.parse_advanced(kwargs["padding"],context) if "padding" in kwargs else 0)
		neg_mask_padding = int(self.Unprompted.parse_advanced(kwargs["neg_padding"],context) if "neg_padding" in kwargs else 0)
		padding_dilation_kernel = None
		if (mask_padding != 0):
			padding_dilation_kernel = numpy.ones((abs(mask_padding), abs(mask_padding)), numpy.uint8)

		neg_padding_dilation_kernel = None
		if (neg_mask_padding != 0):
			neg_padding_dilation_kernel = numpy.ones((abs(neg_mask_padding), abs(neg_mask_padding)), numpy.uint8)

		prompts = content.split(self.Unprompted.Config.syntax.delimiter)
		prompt_parts = len(prompts)

		if "negative_mask" in kwargs:
			negative_prompts = (self.Unprompted.parse_advanced(kwargs["negative_mask"],context)).split(self.Unprompted.Config.syntax.delimiter)
			negative_prompt_parts = len(negative_prompts)
		else: negative_prompts = None

		mask_precision = min(255,int(self.Unprompted.parse_advanced(kwargs["precision"],context) if "precision" in kwargs else 100))
		neg_mask_precision = min(255,int(self.Unprompted.parse_advanced(kwargs["neg_precision"],context) if "neg_precision" in kwargs else 100))

		def overlay_mask_part(img_a,img_b,mode):
			if (mode == "discard"): img_a = ImageChops.darker(img_a, img_b)
			else: img_a = ImageChops.lighter(img_a, img_b)
			return(img_a)

		def gray_to_pil(img):
			return (Image.fromarray(cv2.cvtColor(img,cv2.COLOR_GRAY2RGBA)))

		def process_mask_parts(masks, mode, final_img = None, mask_precision=100, mask_padding=0, padding_dilation_kernel=None, smoothing_kernel=None):
			for i, mask in enumerate(masks):
				filename = f"mask_{mode}_{i}.png"
				plt.imsave(filename,torch.sigmoid(mask[0]))

				# TODO: Figure out how to convert the plot above to numpy instead of re-loading image
				img = cv2.imread(filename)

				if padding_dilation_kernel is not None:
					if (mask_padding > 0): img = cv2.dilate(img,padding_dilation_kernel,iterations=1)
					else: img = cv2.erode(img,padding_dilation_kernel,iterations=1)
				if smoothing_kernel is not None: img = cv2.filter2D(img,-1,smoothing_kernel)

				gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
				(thresh, bw_image) = cv2.threshold(gray_image, mask_precision, 255, cv2.THRESH_BINARY)

				if (mode == "discard"): bw_image = numpy.invert(bw_image)

				# overlay mask parts
				bw_image = gray_to_pil(bw_image)
				if (i > 0 or final_img is not None): bw_image = overlay_mask_part(bw_image,final_img,mode)

				final_img = bw_image
			return(final_img)
			
		def get_mask():
			# load model
			model = CLIPDensePredT(version='ViT-B/16', reduce_dim=64, complex_trans_conv=not self.legacy_weights)
			model_dir = f"{self.Unprompted.base_dir}/lib/stable_diffusion/clipseg/weights"
			os.makedirs(model_dir, exist_ok=True)

			d64_filename = "rd64-uni.pth" if self.legacy_weights else "rd64-uni-refined.pth"
			d64_file = f"{model_dir}/{d64_filename}"
			d16_file = f"{model_dir}/rd16-uni.pth"

			# Download model weights if we don't have them yet
			if not os.path.exists(d64_file):
				print("Downloading clipseg model weights...")
				self.Unprompted.download_file(d64_file,f"https://owncloud.gwdg.de/index.php/s/ioHbRzFx6th32hn/download?path=%2F&files={d64_filename}")
				self.Unprompted.download_file(d16_file,"https://owncloud.gwdg.de/index.php/s/ioHbRzFx6th32hn/download?path=%2F&files=rd16-uni.pth")

			# non-strict, because we only stored decoder weights (not CLIP weights)
			model.load_state_dict(torch.load(d64_file), strict=False);	
			model = model.eval().to(device=device)

			transform = transforms.Compose([
				transforms.ToTensor(),
				transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
				transforms.Resize((512, 512)),
			])
			flattened_input = flatten(self.Unprompted.shortcode_user_vars["init_images"][0], opts.img2img_background_color)
			img = transform(flattened_input).unsqueeze(0)

			# predict
			with torch.no_grad():
				preds = model(img.repeat(prompt_parts,1,1,1).to(device=device), prompts)[0].cpu()
				if (negative_prompts): negative_preds = model(img.repeat(negative_prompt_parts,1,1,1).to(device=device), negative_prompts)[0].cpu()

			if "image_mask" not in self.Unprompted.shortcode_user_vars: self.Unprompted.shortcode_user_vars["image_mask"] = None
			
			if (brush_mask_mode == "add" and self.Unprompted.shortcode_user_vars["image_mask"] is not None):
				final_img = self.Unprompted.shortcode_user_vars["image_mask"].convert("RGBA").resize((512,512))
			else: final_img = None

			# process masking
			final_img = process_mask_parts(preds,"add",final_img, mask_precision, mask_padding, padding_dilation_kernel, smoothing_kernel)

			# process negative masking
			if (brush_mask_mode == "subtract" and self.Unprompted.shortcode_user_vars["image_mask"] is not None):
				self.Unprompted.shortcode_user_vars["image_mask"] = ImageOps.invert(self.Unprompted.shortcode_user_vars["image_mask"])
				self.Unprompted.shortcode_user_vars["image_mask"] = self.Unprompted.shortcode_user_vars["image_mask"].convert("RGBA").resize((512,512))
				final_img = overlay_mask_part(final_img,self.Unprompted.shortcode_user_vars["image_mask"],"discard")
			if (negative_prompts): final_img = process_mask_parts(negative_preds,"discard",final_img, neg_mask_precision,neg_mask_padding, neg_padding_dilation_kernel, neg_smoothing_kernel)

			if "size_var" in kwargs:
				img_data = final_img.load()
				# Count number of transparent pixels
				black_pixels = 0
				total_pixels = 512 * 512
				for y in range(512):
					for x in range(512):
						pixel_data = img_data[x,y]
						if (pixel_data[0] == 0 and pixel_data[1] == 0 and pixel_data[2] == 0): black_pixels += 1
				subject_size = 1 - black_pixels / total_pixels
				self.Unprompted.shortcode_user_vars[kwargs["size_var"]] = subject_size

			return final_img

		# Set up processor parameters correctly
		self.image_mask = get_mask().resize((self.Unprompted.shortcode_user_vars["init_images"][0].width,self.Unprompted.shortcode_user_vars["init_images"][0].height))
		self.Unprompted.shortcode_user_vars["mode"] = 1
		self.Unprompted.shortcode_user_vars["mask_mode"] = 1
		self.Unprompted.shortcode_user_vars["image_mask"] =self.image_mask
		self.Unprompted.shortcode_user_vars["mask_for_overlay"] = self.image_mask
		self.Unprompted.shortcode_user_vars["latent_mask"] = None # fixes inpainting full resolution

		if "save" in kwargs: self.image_mask.save(f"{self.Unprompted.parse_advanced(kwargs['save'],context)}.png")

		return ""
	
	def after(self,p=None,processed=None):
		if self.image_mask and self.show:
			processed.images.append(self.image_mask)
			
			overlayed_init_img = draw_segmentation_masks(pil_to_tensor(p.init_images[0]), pil_to_tensor(self.image_mask.convert("L")) > 0)
			processed.images.append(to_pil_image(overlayed_init_img))
			self.image_mask = None
			self.show = False
			return processed
	
	def ui(self,gr):
		gr.Radio(label="Mask blend mode 🡢 mode",choices=["add","subtract","discard"],value="add",interactive=True)
		gr.Checkbox(label="Show mask in output 🡢 show")
		gr.Checkbox(label="Use legacy weights 🡢 legacy_weights")
		gr.Number(label="Precision of selected area 🡢 precision",value=100,interactive=True)
		gr.Number(label="Precision of negative selected area 🡢 neg_precision",value=100,interactive=True)
		gr.Number(label="Padding radius in pixels 🡢 padding",value=0,interactive=True)
		gr.Number(label="Padding radius in pixels for negative mask 🡢 neg_padding",value=0,interactive=True)
		gr.Number(label="Smoothing radius in pixels 🡢 smoothing",value=20,interactive=True)
		gr.Number(label="Smoothing radius in pixels 🡢 neg_smoothing",value=20,interactive=True)
		gr.Textbox(label="Negative mask prompt 🡢 negative_mask",max_lines=1)
		gr.Textbox(label="Save the mask size to the following variable 🡢 size_var",max_lines=1)